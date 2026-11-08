// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract TuniSovereignLedger {
    struct VerifiedSettlement {
        bytes32 zkCommitmentHash;
        string governorate;
        string agentThreadId;
        uint256 allocatedUnits;
        uint256 maxQuotaUnits;
        uint256 timestamp;
        address verifierAgent;
    }

    mapping(bytes32 => VerifiedSettlement) public settlements;
    bytes32[] public settlementHashes;

    event SettlementAnchored(
        bytes32 indexed zkCommitmentHash,
        string governorate,
        string agentThreadId,
        uint256 allocatedUnits,
        uint256 timestamp
    );

    function anchorZKSettlement(
        bytes32 _zkCommitmentHash,
        string calldata _governorate,
        string calldata _agentThreadId,
        uint256 _allocatedUnits,
        uint256 _maxQuotaUnits
    ) external {
        require(_allocatedUnits <= _maxQuotaUnits, "Quota breach rejected by smart contract");
        require(settlements[_zkCommitmentHash].timestamp == 0, "Commitment already anchored");

        settlements[_zkCommitmentHash] = VerifiedSettlement({
            zkCommitmentHash: _zkCommitmentHash,
            governorate: _governorate,
            agentThreadId: _agentThreadId,
            allocatedUnits: _allocatedUnits,
            maxQuotaUnits: _maxQuotaUnits,
            timestamp: block.timestamp,
            verifierAgent: msg.sender
        });
        settlementHashes.push(_zkCommitmentHash);
        emit SettlementAnchored(_zkCommitmentHash, _governorate, _agentThreadId, _allocatedUnits, block.timestamp);
    }
}
