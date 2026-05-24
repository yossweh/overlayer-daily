#!/usr/bin/env python3
"""
Overlayer Testnet Daily Transaction Script
Runs mint C+ + stake C+ + mint T+ to accumulate on-chain transactions.
Checks points via API and reports status.
"""

import os
import sys
import time
import json
import requests
from web3 import Web3
from eth_abi import encode, decode
from eth_account.messages import encode_defunct

# === CONFIG ===
PK = os.environ.get("AGENT_WALLET_PRIVATE_KEY", "92303bc9c2d311b16428c2d77207f14d2566f60e42522d0653eb85de1fd54e0f")
AGENT = "0x308013F0b23E461792e1c6c67509bEF6E23b84E5"
RPC = "https://sepolia.drpc.org"
BASE_URL = "https://api.overlayer.fi"
GAS_PRICE_GWEI = 3

# Contract addresses
C_PLUS = "0xE815718D44694ec4637CB775C468d87f6e15B538"
T_PLUS = "0xe20534a32f9162488a90026F268a74fBE28d272D"
USDC = "0x94a9D9AC8a22534E3FaCa9F4e7F2E2cf85d5E4C8"
USDT = "0xaA8E23Fb1079EA71e0a56F48a2aA51851D8433D0"
SC_PLUS = "0x753937137Eb92871A6F3517514d4f1Ee860e3FDF"

# Selectors
MINT_SEL = bytes.fromhex("2ef6f1ab")  # mint((address,address,address,uint256,uint256))
DEPOSIT_SEL = "6e553f65"  # deposit(uint256,address)
TRANSFER_SEL = "a9059cbb"  # transfer(address,uint256)

# ERC20 minimal ABI
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
]


def connect():
    w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        raise Exception("Cannot connect to RPC")
    return w3


def auth_overlayer(w3):
    acct = w3.eth.account.from_key(PK)
    nonce_resp = requests.get(f"{BASE_URL}/api-s/auth/nonce/{AGENT}", timeout=15)
    if nonce_resp.status_code != 200:
        raise Exception(f"Nonce failed: {nonce_resp.status_code}")
    nonce_val = nonce_resp.json()["nonce"]
    expiry = int(time.time()) + 300
    msg = f"Request Overlayer social session\n{AGENT}\n{expiry}\n{nonce_val}"
    signed = acct.sign_message(encode_defunct(text=msg))
    sig = "0x" + signed.signature.hex()
    verify_resp = requests.post(f"{BASE_URL}/api-s/auth/verify/{AGENT}", json={"message": msg, "signature": sig}, timeout=15)
    if verify_resp.status_code != 200:
        raise Exception(f"Auth failed: {verify_resp.status_code} - {verify_resp.text[:200]}")
    return verify_resp.json()["token"]


def get_points(token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(f"{BASE_URL}/api-s/socials/onchain-tasks/points/{AGENT}", headers=headers, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("totalPoints", 0)
    return -1


def get_balances(w3):
    usdc = w3.eth.contract(address=USDC, abi=ERC20_ABI)
    usdt = w3.eth.contract(address=USDT, abi=ERC20_ABI)
    cplus = w3.eth.contract(address=C_PLUS, abi=ERC20_ABI)
    scplus = w3.eth.contract(address=SC_PLUS, abi=ERC20_ABI)
    tplus = w3.eth.contract(address=T_PLUS, abi=ERC20_ABI)
    eth_bal = w3.from_wei(w3.eth.get_balance(AGENT), "ether")
    return {
        "ETH": float(eth_bal),
        "USDC": usdc.functions.balanceOf(AGENT).call() / 10**6,
        "USDT": usdt.functions.balanceOf(AGENT).call() / 10**6,
        "C+": cplus.functions.balanceOf(AGENT).call() / 10**18,
        "sC+": scplus.functions.balanceOf(AGENT).call() / 10**18,
        "T+": tplus.functions.balanceOf(AGENT).call() / 10**18,
    }


def ensure_allowance(w3, token_addr, spender, amount):
    token = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    allowance = token.functions.allowance(AGENT, spender).call()
    if allowance >= amount:
        return None
    approve_data = "0x" + "095ea7b3" + encode(["address", "uint256"], [spender, 2**256 - 1]).hex()
    nonce = w3.eth.get_transaction_count(AGENT)
    gas_price = max(w3.eth.gas_price, int(GAS_PRICE_GWEI * 1e9))
    tx = {"from": AGENT, "to": token_addr, "data": approve_data, "gas": 100000, "gasPrice": gas_price, "nonce": nonce, "chainId": 11155111}
    signed = w3.eth.account.sign_transaction(tx, PK)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    return receipt


def send_tx(w3, to, data, gas=200000, value=0):
    nonce = w3.eth.get_transaction_count(AGENT)
    gas_price = max(w3.eth.gas_price, int(GAS_PRICE_GWEI * 1e9))
    tx = {"from": AGENT, "to": to, "data": data, "gas": gas, "gasPrice": gas_price, "nonce": nonce, "chainId": 11155111}
    if value:
        tx["value"] = value
    signed = w3.eth.account.sign_transaction(tx, PK)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    return receipt, tx_hash.hex()


def batch_send(w3, to, data_list, gas=200000):
    """Send multiple TXs in sequence, return all receipts."""
    base_nonce = w3.eth.get_transaction_count(AGENT)
    gas_price = max(w3.eth.gas_price, int(GAS_PRICE_GWEI * 1e9))
    tx_hashes = []
    for i, data in enumerate(data_list):
        nonce = base_nonce + i
        tx = {"from": AGENT, "to": to, "data": data, "gas": gas, "gasPrice": gas_price, "nonce": nonce, "chainId": 11155111}
        signed = w3.eth.account.sign_transaction(tx, PK)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hashes.append(tx_hash.hex())
    confirmed = 0
    for h in tx_hashes:
        for _ in range(60):
            try:
                receipt = w3.eth.get_transaction_receipt(f"0x{h}")
                if receipt.status == 1:
                    confirmed += 1
                break
            except:
                time.sleep(2)
    return confirmed, len(tx_hashes), tx_hashes


def mint_cplus(w3, count=15, amount_usdc=1):
    """Mint C+ by depositing USDC."""
    mint_usdc = amount_usdc * 10**6
    mint_cplus = amount_usdc * 10**18
    order = (AGENT, AGENT, USDC, mint_usdc, mint_cplus)
    calldata = "0x" + (MINT_SEL + encode(["(address,address,address,uint256,uint256)"], [order])).hex()
    data_list = [calldata] * count
    return batch_send(w3, C_PLUS, data_list)


def mint_tplus(w3, count=15, amount_usdt=1):
    """Mint T+ by depositing USDT."""
    mint_usdt = amount_usdt * 10**6
    mint_tplus = amount_usdt * 10**18
    order = (AGENT, AGENT, USDT, mint_usdt, mint_tplus)
    calldata = "0x" + (MINT_SEL + encode(["(address,address,address,uint256,uint256)"], [order])).hex()
    data_list = [calldata] * count
    return batch_send(w3, T_PLUS, data_list)


def stake_cplus(w3, amount):
    """Stake C+ into sC+."""
    stake_amount = int(amount * 10**18)
    deposit_data = "0x" + DEPOSIT_SEL + encode(["uint256", "address"], [stake_amount, AGENT]).hex()
    return send_tx(w3, SC_PLUS, deposit_data, gas=500000)


def main():
    print("=== Overlayer Daily Transactions ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

    w3 = connect()
    print(f"Connected to Sepolia (block {w3.eth.block_number})")

    # Check balances before
    bal_before = get_balances(w3)
    print(f"\nBalances:")
    for k, v in bal_before.items():
        print(f"  {k}: {v}")

    tx_count = 0
    results = []

    # 1. Mint 15 C+ (1 USDC each)
    if bal_before["USDC"] >= 15:
        print(f"\nMinting 15 x 1 C+...")
        ensure_allowance(w3, USDC, C_PLUS, 15 * 10**6)
        confirmed, total, hashes = mint_cplus(w3, count=15, amount_usdc=1)
        tx_count += confirmed
        results.append(f"Mint C+: {confirmed}/{total} confirmed")
        print(f"  {confirmed}/{total} confirmed")
    else:
        print(f"\nInsufficient USDC ({bal_before['USDC']}) for minting")

    # 2. Stake all C+ (except keep 1 C+ for gas)
    cplus_bal = w3.eth.contract(address=C_PLUS, abi=ERC20_ABI).functions.balanceOf(AGENT).call()
    if cplus_bal > 10**18:
        stake_amount = w3.from_wei(cplus_bal - 10**18, "ether")
        print(f"\nStaking {stake_amount} C+...")
        ensure_allowance(w3, C_PLUS, SC_PLUS, cplus_bal)
        receipt, tx_hash = stake_cplus(w3, float(stake_amount))
        tx_count += 1 if receipt.status == 1 else 0
        results.append(f"Stake C+: {'SUCCESS' if receipt.status == 1 else 'FAILED'}")
        print(f"  {'SUCCESS' if receipt.status == 1 else 'FAILED'}")
    else:
        print(f"\nInsufficient C+ ({w3.from_wei(cplus_bal, 'ether')}) for staking")

    # 3. Mint 15 T+ (1 USDT each)
    usdt_bal = w3.eth.contract(address=USDT, abi=ERC20_ABI).functions.balanceOf(AGENT).call()
    if usdt_bal >= 15 * 10**6:
        print(f"\nMinting 15 x 1 T+...")
        ensure_allowance(w3, USDT, T_PLUS, 15 * 10**6)
        confirmed, total, hashes = mint_tplus(w3, count=15, amount_usdt=1)
        tx_count += confirmed
        results.append(f"Mint T+: {confirmed}/{total} confirmed")
        print(f"  {confirmed}/{total} confirmed")
    else:
        print(f"\nInsufficient USDT ({usdt_bal / 10**6}) for minting")

    # 4. Auth and check points
    try:
        token = auth_overlayer(w3)
        points = get_points(token)
        print(f"\nOverlayer points: {points}")
    except Exception as e:
        points = "error"
        print(f"\nOverlayer API error: {e}")

    # 5. Balances after
    bal_after = get_balances(w3)
    print(f"\nBalances after:")
    for k, v in bal_after.items():
        print(f"  {k}: {v}")

    total_nonce = w3.eth.get_transaction_count(AGENT)
    print(f"\nTotal transactions (nonce): {total_nonce}")
    print(f"TXs this run: {tx_count}")

    # Build report
    report = f"""Overlayer Daily Report
Date: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}
Points: {points}
TXs this run: {tx_count}
Total nonce: {total_nonce}

Balances:
  ETH: {bal_after['ETH']:.4f}
  USDC: {bal_after['USDC']:.1f}
  USDT: {bal_after['USDT']:.1f}
  C+: {bal_after['C+']:.1f}
  sC+: {bal_after['sC+']:.1f}
  T+: {bal_after['T+']:.1f}

Results:
  {chr(10)+'  '.join(results)}"""

    print(f"\n{report}")
    return report


if __name__ == "__main__":
    main()
