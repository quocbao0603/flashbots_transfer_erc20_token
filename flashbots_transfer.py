'''
Simple flashbots bundle to rescue a hacked wallet
  . Send ETH to wallet
  . Transfer ERC20 token out of wallet
'''

from brownie import accounts, network, Contract
from eth_account import Account
from eth_account.signers.local import LocalAccount
from flashbots import flashbot
from web3 import Web3, HTTPProvider
from web3.exceptions import TransactionNotFound
from web3.types import TxParams

MAINNET_URL = 'https://mainnet.infura.io/v3/3a7237265fc64c3e9e36508511ac7ccd'
KEEY_SMC = '0xeC0d95b4273325E0d3c1605908f1c4027CCc8a7A'
DEST_ADDR = '0x98549072F2c573344054e43Ee9D05eD884719315'

KEEY_AMOUNT = 1

# Load local wallets already imported to Brownie
f_id = accounts.load('flashbots_id')
test1 = accounts.load('test1')
chau_acc = accounts.load('chau-account')

# Setup flashbot relay
w3 = Web3(HTTPProvider(MAINNET_URL))
signer: LocalAccount = Account.from_key(f_id.private_key)
flashbot(w3, signer)

# Load keey smc from brownie to web3
# FIXME: better way to load from brownie smc to w3 smc, or use one contract obj
network.connect('mainnet')
keey_brownie = Contract(KEEY_SMC)  # KEEY_SMC already loaded to local Brownie db
keey_smc = w3.eth.contract(address=keey_brownie.address, abi=keey_brownie.abi)

# print('Eth network status:', w3.isConnected())

# Tx1: send ETH to Chau wallet
tx1: TxParams = {
    'to': chau_acc.address,
    "value": Web3.toWei(0.09, "ether"),
    "gas": 21000,
    "maxFeePerGas": Web3.toWei(200, "gwei"),
    "maxPriorityFeePerGas": Web3.toWei(50, "gwei"),
    'nonce': w3.eth.get_transaction_count(test1.address),
    'chainId': 1,
    'type': 2
}
tx1_signed = w3.eth.account.sign_transaction(tx1, test1.private_key)

# Tx2: withdraw 1 KEEY token
tx2 = keey_smc.functions.transfer(DEST_ADDR, KEEY_AMOUNT).build_transaction({
    'chainId': 1,
    'gas': 400000,  # High gas for miner reward
    "maxFeePerGas": Web3.toWei(200, "gwei"),
    "maxPriorityFeePerGas": Web3.toWei(50, "gwei"),
    'nonce': w3.eth.get_transaction_count(chau_acc.address),
})
tx2_signed = w3.eth.account.sign_transaction(tx2, chau_acc.private_key)

bundle = [
    {'signed_transaction': tx1_signed.rawTransaction},
    {'signed_transaction': tx2_signed.rawTransaction},
]

# Simulate
try:
    block = w3.eth.block_number
    result = w3.flashbots.simulate(bundle, block)
    print('Simulation result:', 'gasUsed:', result['totalGasUsed'],
          'coinbasediff:', result['coinbaseDiff'])
except Exception as e:
    print("Simulation error", e)
    quit()

# Try to send bundle until miners accept
for i in range(0, 5):
    block = w3.eth.block_number
    print(f"Simulating on block {block}")
    # simulate bundle on current block
    try:
        result = w3.flashbots.simulate(bundle, block)
        print("Simulation successful. Attempt to send bundle")

        # send bundle targeting next block
        print(f"Sending bundle targeting block {block + 1}")
        send_result = w3.flashbots.send_bundle(bundle, target_block_number=block + 1)
        send_result.wait()
        try:
            receipts = send_result.receipts()
            print(f"\nBundle was mined in block {receipts[0].blockNumber}\a")
            break
        except TransactionNotFound:
            print(f"Bundle not found in block {block + 1}")

    except Exception as e:
        print("Simulation error", e)
        break
