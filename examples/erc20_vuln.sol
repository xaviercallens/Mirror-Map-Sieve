// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VulnerableERC20
 * @dev Intentionally buggy ERC-20 for Bourbaki exploit synthesis demo.
 *
 * BUG 1: No overflow check on `balanceOf[to] += amount` — if `to` balance
 *         wraps around, tokens are created from nothing.
 *
 * BUG 2: Missing `require(to != address(0))` — tokens can be burned by
 *         sending to the zero address, violating totalSupply conservation.
 *
 * BUG 3: State update order in transferFrom allows reentrancy-style
 *         double-spend if allowance is updated AFTER the transfer.
 *
 * This contract is designed to make Galois FAIL to prove the solvency
 * theorem, triggering Descartes exploit synthesis.
 */
contract VulnerableERC20 {

    string public name;
    string public symbol;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    constructor(string memory _name, string memory _symbol, uint256 _initialSupply) {
        name = _name;
        symbol = _symbol;
        totalSupply = _initialSupply;
        balanceOf[msg.sender] = _initialSupply;
    }

    // BUG 2: Missing `require(to != address(0))`
    function transfer(address to, uint256 amount) public returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient balance");

        balanceOf[msg.sender] -= amount;
        // BUG 1: No overflow protection on recipient balance
        balanceOf[to] += amount;

        return true;
    }

    function approve(address spender, uint256 amount) public returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    // BUG 3: Allowance updated AFTER state change (reentrancy risk)
    function transferFrom(address from, address to, uint256 amount) public returns (bool) {
        require(balanceOf[from] >= amount, "Insufficient balance");

        balanceOf[from] -= amount;
        balanceOf[to] += amount;

        // Allowance check and update AFTER balance mutation
        require(allowance[from][msg.sender] >= amount, "Allowance exceeded");
        allowance[from][msg.sender] -= amount;

        return true;
    }
}
