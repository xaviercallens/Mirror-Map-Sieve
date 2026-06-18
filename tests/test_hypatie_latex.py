# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit tests for Hypatie's enhanced LaTeX capabilities and Supabase sync."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agents.hypatie.tools.latex_compiler import parse_errors_from_log
from agents.hypatie.tools.latex_synthesizer import generate_latex_source
from agents.hypatie.tools.latex_reviewer import review_and_repair_latex
from agents.hypatie.tools.octree_db_sync import OctreeSyncClient


class TestHypatieLatex(unittest.TestCase):
    """Test suite for Hypatie LaTeX and DB Sync components."""

    def test_log_error_parsing(self) -> None:
        """Verify that line-specific LaTeX compile errors are correctly parsed from log output."""
        mock_log = """
This is pdfTeX, Version 3.141592653-2.6-1.40.25 (TeX Live 2023) (preloaded format=pdflatex)
entering extended mode
(./document.tex
LaTeX2e <2023-06-01> patch level 1
L3 programming layer <2023-05-26>
(/usr/local/texlive/2023/texmf-dist/tex/latex/base/article.cls
Document Class: article 2023/05/17 v1.4n Standard LaTeX document class
)
! Undefined control sequence.
l.42 \\nonexistentcommand
                        
! Missing } inserted.
<to be read again> 
                   \\endgroup 
l.50 \\section{Section Name
                          
)
        """
        errors = parse_errors_from_log(mock_log)
        self.assertEqual(len(errors), 2)
        
        self.assertEqual(errors[0]["line"], 42)
        self.assertEqual(errors[0]["message"], "Undefined control sequence")
        self.assertEqual(errors[0]["context"], "\\nonexistentcommand")

        self.assertEqual(errors[1]["line"], 50)
        self.assertEqual(errors[1]["message"], "Missing } inserted")
        self.assertEqual(errors[1]["context"], "\\section{Section Name")

    @patch("google.genai.Client")
    def test_latex_synthesis_prompts(self, mock_genai_client: MagicMock) -> None:
        """Verify that the synthesizer template routing handles document types properly."""
        mock_instance = MagicMock()
        mock_genai_client.return_value = mock_instance
        
        mock_response = MagicMock()
        mock_response.text = "```latex\n\\documentclass{article}\n\\begin{document}\nHello World\n\\end{document}\n```"
        mock_instance.models.generate_content.return_value = mock_response

        res = generate_latex_source(
            title="Elliptic Curves",
            raw_content="BSD conjecture formulation",
            document_type="research",
        )
        self.assertTrue(res["success"])
        self.assertIn("documentclass", res["latex_code"])
        
        # Verify it made a call
        mock_instance.models.generate_content.assert_called_once()

    @patch("agents.hypatie.tools.latex_reviewer.compile_latex_to_pdf")
    @patch("google.genai.Client")
    def test_self_healing_repair_loop(self, mock_genai_client: MagicMock, mock_compile: MagicMock) -> None:
        """Verify that the self-healing loop runs compilation checks and repairs on failure."""
        mock_instance = MagicMock()
        mock_genai_client.return_value = mock_instance
        
        # Simulate compilation failure on iteration 0, success on iteration 1
        mock_compile.side_effect = [
            {"success": False, "pdf_path": None, "errors": [{"line": 10, "message": "Syntax error", "context": ""}], "logs": ""},
            {"success": True, "pdf_path": "/tmp/document.pdf", "errors": [], "logs": ""},
        ]
        
        mock_response = MagicMock()
        mock_response.text = "```latex\nFixed LaTeX Code\n```"
        mock_instance.models.generate_content.return_value = mock_response

        res = review_and_repair_latex(
            latex_code="Broken LaTeX Code",
            focus_errors="Fix syntax",
            max_iterations=3
        )
        
        self.assertTrue(res["success"])
        self.assertEqual(res["repaired_code"], "Fixed LaTeX Code")
        self.assertEqual(res["iterations"], 1)

    @patch("httpx.Client")
    def test_octree_sync_pull(self, mock_httpx_client: MagicMock) -> None:
        """Verify the OctreeSyncClient constructs requests and parses pull details."""
        mock_instance = MagicMock()
        mock_httpx_client.return_value.__enter__.return_value = mock_instance
        
        # Mock pulling files metadata
        mock_instance.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"id": "file1", "name": "main.tex", "project_id": "proj123"},
                {"id": "file2", "name": "intro.tex", "project_id": "proj123"},
            ]
        )
        
        client = OctreeSyncClient(
            supabase_url="https://xyz.supabase.co",
            supabase_key="anonkey",
            auth_token="token"
        )
        
        files_list = client.pull_project_files_list("proj123")
        self.assertEqual(len(files_list), 2)
        self.assertEqual(files_list[0]["name"], "main.tex")


if __name__ == "__main__":
    unittest.main()
