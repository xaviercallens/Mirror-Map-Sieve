# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Type Mapper — Source Language Types → Lean 4 / Mathlib4 Types.

Maps imperative language types to their Lean 4 algebraic equivalents
per the Bourbaki Translation Layer specification.
"""

from __future__ import annotations


class TypeMapper:
    """Maps source language types to Lean 4 types.

    Supports Solidity, Python, Rust, and C++ type systems.
    Defaults to opaque type aliases for unknown types.
    """

    # Solidity → Lean 4 type mappings
    _SOLIDITY_MAP: dict[str, str] = {
        # Unsigned integers
        "uint": "Std.Data.BitVec 256",
        "uint8": "Std.Data.BitVec 8",
        "uint16": "Std.Data.BitVec 16",
        "uint32": "Std.Data.BitVec 32",
        "uint64": "Std.Data.BitVec 64",
        "uint128": "Std.Data.BitVec 128",
        "uint256": "Std.Data.BitVec 256",
        # Signed integers
        "int": "Int",
        "int8": "Int",
        "int16": "Int",
        "int32": "Int",
        "int64": "Int",
        "int128": "Int",
        "int256": "Int",
        # Address & bool
        "address": "Nat",  # Addresses are 160-bit unsigned integers
        "bool": "Bool",
        # Bytes
        "bytes": "ByteArray",
        "bytes32": "ByteArray",
        "string": "String",
    }

    # Python → Lean 4 type mappings
    _PYTHON_MAP: dict[str, str] = {
        "int": "Int",
        "float": "Float",
        "str": "String",
        "bool": "Bool",
        "list": "List",
        "dict": "Std.HashMap",
        "set": "Finset",
        "tuple": "Prod",
        "None": "Unit",
        "bytes": "ByteArray",
    }

    # Rust → Lean 4 type mappings
    _RUST_MAP: dict[str, str] = {
        "u8": "Fin (2 ^ 8)",
        "u16": "Fin (2 ^ 16)",
        "u32": "Fin (2 ^ 32)",
        "u64": "Fin (2 ^ 64)",
        "u128": "Fin (2 ^ 128)",
        "usize": "Nat",
        "i8": "Int",
        "i16": "Int",
        "i32": "Int",
        "i64": "Int",
        "i128": "Int",
        "isize": "Int",
        "f32": "Float",
        "f64": "Float",
        "bool": "Bool",
        "String": "String",
        "Vec": "Array",
        "HashMap": "Std.HashMap",
        "Option": "Option",
        "Result": "Except",
    }

    _LANGUAGE_MAPS: dict[str, dict[str, str]] = {
        "solidity": _SOLIDITY_MAP,
        "python": _PYTHON_MAP,
        "rust": _RUST_MAP,
    }

    def map_type(
        self,
        source_type: str,
        language: str = "solidity",
    ) -> str:
        """Map a source language type to its Lean 4 equivalent.

        Args:
            source_type: Type name in the source language.
            language: Source language identifier.

        Returns:
            Lean 4 type string.
        """
        lang = language.lower()
        type_map = self._LANGUAGE_MAPS.get(lang, {})

        # Handle mapping types specially
        if source_type.startswith("mapping("):
            # mapping(K => V) → Std.HashMap K V
            inner = source_type[len("mapping(") : -1]
            parts = inner.split("=>")
            if len(parts) == 2:
                key_type = self.map_type(parts[0].strip(), language)
                val_type = self.map_type(parts[1].strip(), language)
                return f"Std.HashMap {key_type} {val_type}"

        # Handle generic types: List<T>, Vec<T>, etc.
        if "<" in source_type:
            base = source_type.split("<")[0].strip()
            inner = source_type[source_type.index("<") + 1 : source_type.rindex(">")]
            lean_base = type_map.get(base, base)
            lean_inner = self.map_type(inner.strip(), language)
            return f"{lean_base} {lean_inner}"

        # Direct lookup
        lean_type = type_map.get(source_type)
        if lean_type:
            return lean_type

        # Fallback: use the type name as an opaque alias
        return source_type

    def map_params(
        self,
        params: dict[str, str],
        language: str = "solidity",
    ) -> dict[str, str]:
        """Map a dict of parameter names → source types to Lean 4 types.

        Args:
            params: {param_name: source_type} from ParsedFunction.
            language: Source language identifier.

        Returns:
            {param_name: lean_type} mapping.
        """
        return {
            name: self.map_type(stype, language)
            for name, stype in params.items()
        }
