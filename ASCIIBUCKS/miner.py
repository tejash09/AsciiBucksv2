import time
import hashlib
import json
import requests
import base64
from flask import Flask, request,render_template
from multiprocessing import Process, Pipe
import ecdsa

from miner_config import MINER_ADDRESS, MINER_NODE_URL, PEER_NODES

node = Flask(__name__)

class Block:
    def __init__(self, index, timestamp, data, previous_hash):
        """
        Initialize a new blockchain block.

        Parameters
        ----------
        index : int
            The index of the block in the blockchain.
        timestamp : float
            The timestamp when the block was created.
        data : dict
            Data associated with the block, including proof-of-work
            and transactions.
        previous_hash : str
            The hash of the previous block in the blockchain.

        Attributes
        ----------
        index : int
            The index of the block in the blockchain.
        timestamp : float
            The timestamp when the block was created.
        data : dict
            Data associated with the block, including proof-of-work
            and transactions.
        previous_hash : str
            The hash of the previous block in the blockchain.
        hash : str
            The hash of the current block.

        Returns
        -------
        None

        Notes
        -----
        This class represents a block in the blockchain. It stores
        the block's index, timestamp, data, previous_hash, and
        computes the hash of the block based on its attributes.
        """
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self.hash_block()

    def hash_block(self):
        """
        Calculate the hash of the current block.

        Returns
        -------
        str
            The hash of the current block.

        Notes
        -----
        This method calculates the hash of the block based on its
        index, timestamp, data, and the hash of the previous block.
        It returns the calculated hash as a hexadecimal string.
        """
        sha = hashlib.sha256()
        sha.update((str(self.index) + str(self.timestamp) + str(self.data) + str(self.previous_hash)).encode('utf-8'))
        return sha.hexdigest()

def create_genesis_block():
    """
    Create the genesis block for the blockchain.

    Returns
    -------
    Block
        The genesis block of the blockchain.

    Notes
    -----
    This function creates the first block in the blockchain, known
    as the genesis block. It initializes the block with specific
    data, including a proof-of-work value and no transactions.
    """
    return Block(0, time.time(), {
        "proof-of-work": 9,
        "transactions": None},
        "0")

BLOCKCHAIN = [create_genesis_block()]
NODE_PENDING_TRANSACTIONS = []

def proof_of_work(last_proof, blockchain):
    """
    Perform proof of work to mine a new block.

    Parameters
    ----------
    last_proof : int
        The proof-of-work value of the previous block.
    blockchain : list
        The current blockchain.

    Returns
    -------
    int or (bool, list)
        If successful, the new proof-of-work value; otherwise,
        a tuple indicating failure and a potential updated
        blockchain.

    Notes
    -----
    This function attempts to find a new proof-of-work value
    that meets specific criteria based on the last_proof value.
    It continues searching until a valid value is found. If it
    takes too long, it may update the blockchain via consensus
    and return a failure indicator along with the updated
    blockchain.
    """
    incrementer = last_proof + 1
    start_time = time.time()
    while not (incrementer % 7919 == 0 and incrementer % last_proof == 0):
        incrementer += 1
        if int((time.time()-start_time) % 60) == 0:
            new_blockchain = consensus(blockchain)
            if new_blockchain:
                return False, new_blockchain
    return incrementer, blockchain

def mine(a, blockchain, node_pending_transactions):
    """
    Mine new blocks for the blockchain.

    Parameters
    ----------
    a : multiprocessing.Connection
        A connection for sending data to the parent process.
    blockchain : list
        The current blockchain.
    node_pending_transactions : list
        The list of pending transactions in the node.

    Returns
    -------
    None

    Notes
    -----
    This function continuously mines new blocks for the blockchain.
    It calculates the proof-of-work, includes pending transactions,
    and adds the new block to the blockchain. It also updates
    the pending transactions and broadcasts new blocks to other
    nodes.
    """
    BLOCKCHAIN = blockchain
    NODE_PENDING_TRANSACTIONS = node_pending_transactions
    while True:
        last_block = BLOCKCHAIN[-1]
        last_proof = last_block.data['proof-of-work']
        proof = proof_of_work(last_proof, BLOCKCHAIN)
        if not proof[0]:
            BLOCKCHAIN = proof[1]
            a.send(BLOCKCHAIN)
            continue
        else:
            NODE_PENDING_TRANSACTIONS = requests.get(url=MINER_NODE_URL + '/txion', params={'update': MINER_ADDRESS}).content
            NODE_PENDING_TRANSACTIONS = json.loads(NODE_PENDING_TRANSACTIONS)
            NODE_PENDING_TRANSACTIONS.append({
                "from": "network",
                "to": MINER_ADDRESS,
                "amount": 1})
            new_block_data = {
                "proof-of-work": proof[0],
                "transactions": list(NODE_PENDING_TRANSACTIONS)
            }
            new_block_index = last_block.index + 1
            new_block_timestamp = time.time()
            last_block_hash = last_block.hash
            NODE_PENDING_TRANSACTIONS = []
            mined_block = Block(new_block_index, new_block_timestamp, new_block_data, last_block_hash)
            BLOCKCHAIN.append(mined_block)
            print(json.dumps({
              "index": new_block_index,
              "timestamp": str(new_block_timestamp),
              "data": new_block_data,
              "hash": last_block_hash
            }, sort_keys=True) + "\n")
            a.send(BLOCKCHAIN)
            requests.get(url=MINER_NODE_URL + '/blocks', params={'update': MINER_ADDRESS})

def find_new_chains():
    """
    Find and retrieve longer blockchain chains from peers.

    Returns
    -------
    list
        A list of potential longer blockchain chains.

    Notes
    -----
    This function checks other nodes (peers) for their blockchain
    chains and validates them. It returns a list of potential
    longer chains.
    """
    other_chains = []
    for node_url in PEER_NODES:
        block = requests.get(url=node_url + "/blocks").content
        block = json.loads(block)
        validated = validate_blockchain(block)
        if validated:
            other_chains.append(block)
    return other_chains

def consensus(blockchain):
    """
    Achieve consensus with other nodes for the blockchain.

    Parameters
    ----------
    blockchain : list
        The current blockchain.

    Returns
    -------
    list or bool
        If consensus is reached, the updated blockchain; otherwise,
        False.

    Notes
    -----
    This function attempts to achieve consensus with other nodes
    by comparing the current blockchain with potential longer
    chains. If a longer chain is found, it updates the blockchain.
    If consensus is not reached, it returns False.
    """
    other_chains = find_new_chains()
    BLOCKCHAIN = blockchain
    longest_chain = BLOCKCHAIN
    for chain in other_chains:
        if len(longest_chain) < len(chain):
            longest_chain = chain
    if longest_chain == BLOCKCHAIN:
        return False
    else:
        BLOCKCHAIN = longest_chain
        return BLOCKCHAIN

def validate_blockchain(blockchain):
    """
    Validate a blockchain chain.

    Parameters
    ----------
    blockchain : list
        The blockchain chain to be validated.

    Returns
    -------
    bool
        True if the blockchain chain is valid; otherwise, False.

    Notes
    -----
    This function validates a blockchain chain by checking the
    integrity of each block, including the index, timestamp, data,
    previous_hash, and hash values. It also verifies the proof-of-work.

    Returns True if the blockchain chain is valid; otherwise, False.
    """
    for i in range(1, len(blockchain)):
        current_block = blockchain[i]
        previous_block = blockchain[i - 1]

        if current_block.index != previous_block.index + 1:
            return False

        if current_block.timestamp <= previous_block.timestamp:
            return False

        if current_block.hash_block() != current_block.hash:
            return False

        if current_block.previous_hash != previous_block.hash:
            return False

        if not valid_proof(previous_block.data['proof-of-work'], current_block.data['proof-of-work']):
            return False

    return True

def valid_proof(last_proof, proof):
    """
    Validate a new proof-of-work.

    Parameters
    ----------
    last_proof : int
        The proof-of-work value of the previous block.
    proof : int
        The new proof-of-work value to be validated.

    Returns
    -------
    bool
        True if the proof is valid; otherwise, False.

    Notes
    -----
    This function validates a new proof-of-work value by checking
    whether it meets specific criteria based on the last_proof value.
    """
    return (proof % 7919 == 0) and (proof % last_proof == 0)

@node.route('/blocks', methods=['GET'])
def get_blocks():
    """
    Get the blockchain in JSON format.

    Returns
    -------
    str
        The JSON representation of the blockchain.

    Notes
    -----
    This route allows other nodes to request the blockchain.
    It returns the blockchain in JSON format.
    """
    if request.args.get("update") == MINER_ADDRESS:
        global BLOCKCHAIN
        BLOCKCHAIN = pipe_input.recv()
    chain_to_send = BLOCKCHAIN
    chain_to_send_json = []
    for block in chain_to_send:
        block = {
            "index": str(block.index),
            "timestamp": str(block.timestamp),
            "data": str(block.data),
            "hash": block.hash
        }
        chain_to_send_json.append(block)
    chain_to_send = json.dumps(chain_to_send_json, sort_keys=True)
    return chain_to_send

@node.route('/txion', methods=['GET', 'POST'])
def transaction():
    """
    Handle transaction requests.

    Returns
    -------
    str
        A message indicating the success or failure of a transaction.

    Notes
    -----
    This route handles both GET and POST requests for transactions.
    For POST requests, it validates the signature and processes
    the transaction. For GET requests, it returns pending transactions.
    """
    if request.method == 'POST':
        new_txion = request.get_json()
        if validate_signature(new_txion['from'], new_txion['signature'], new_txion['message']):
            NODE_PENDING_TRANSACTIONS.append(new_txion)
            print("New transaction")
            print("FROM: {0}".format(new_txion['from']))
            print("TO: {0}".format(new_txion['to']))
            print("AMOUNT: {0}\n".format(new_txion['amount']))
            return "Transaction submission successful\n"
        else:
            return "Transaction submission failed. Wrong signature\n"
    elif request.method == 'GET' and request.args.get("update") == MINER_ADDRESS:
        pending = json.dumps(NODE_PENDING_TRANSACTIONS, sort_keys=True)
        NODE_PENDING_TRANSACTIONS[:] = []
        return pending

def validate_signature(public_key, signature, message):
    """
    Validate a transaction's digital signature.

    Parameters
    ----------
    public_key : str
        The public key used to verify the signature.
    signature : str
        The digital signature to be verified.
    message : str
        The message that was signed.

    Returns
    -------
    bool
        True if the signature is valid; otherwise, False.

    Notes
    -----
    This function validates a digital signature using the provided
    public key, signature, and message. It returns True if the
    signature is valid and False if it is not.
    """
    public_key = (base64.b64decode(public_key)).hex()
    signature = base64.b64decode(signature)
    vk = ecdsa.VerifyingKey.from_string(bytes.fromhex(public_key), curve=ecdsa.SECP256k1)
    try:
        return vk.verify(signature, message.encode())
    except:
        return False

def welcome_msg():
    """
    Print a welcome message to the console.

    Returns
    -------
    None

    Notes
    -----
    This function prints a welcome message to the console when
    the script is executed.
    """
    print("""       =========================================\n
        ASCII BUCKS v1.0.0 - BLOCKCHAIN SYSTEM\n
       =========================================\n\n\n\n\n""")
@node.route('/')
def index():
    return render_template('index.html')
if __name__ == '__main__':
    welcome_msg()
    pipe_output, pipe_input = Pipe()
    miner_process = Process(target=mine, args=(pipe_output, BLOCKCHAIN, NODE_PENDING_TRANSACTIONS))
    miner_process.start()
    transactions_process = Process(target=node.run(), args=pipe_input)
    transactions_process.start()
    
