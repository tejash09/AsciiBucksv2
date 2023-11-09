import requests
import time
import base64
import ecdsa
import json

def wallet():
    """
    Start the Simple Coin blockchain wallet application.

    This function provides a command-line interface for interacting
    with a Simple Coin blockchain, allowing users to generate new
    wallets, send coins to other wallets, check transactions, or
    quit the application.

    Returns
    -------
    None

    Notes
    -----
    The wallet application interacts with a local Simple Coin
    blockchain node running at 'http://localhost:5000'. Ensure that
    the blockchain node is running and accessible for the wallet
    to work correctly.

    The application guides the user through different options,
    such as generating a new wallet, sending coins, and checking
    transactions, using a simple text-based menu.
    """
    response = None
    while response not in ["1", "2", "3", "4"]:
        response = input("""What do you want to do?
        1. Generate a new wallet
        2. Send coins to another wallet
        3. Check transactions
        4. Quit\n""")
    if response == "1":
        generate_ECDSA_keys()
    elif response == "2":
        addr_from = input("From: introduce your wallet address (public key)\n")
        private_key = input("Introduce your private key\n")
        addr_to = input("To: introduce destination wallet address\n")
        amount = input("Amount: number stating how much you want to send\n")
        print("=========================================\n\n")
        print("Is everything correct?\n")
        print(F"From: {addr_from}\nPrivate Key: {private_key}\nTo: {addr_to}\nAmount: {amount}\n")
        response = input("y/n\n")
        if response.lower() == "y":
            send_transaction(addr_from, private_key, addr_to, amount)
        elif response.lower() == "n":
            return wallet()  # return to the main menu
    elif response == "3":
        check_transactions()
        return wallet()  # return to the main menu
    else:
        quit()

def send_transaction(addr_from, private_key, addr_to, amount):
    """
    Send coins from one wallet to another.

    This function sends a specified amount of coins from one wallet
    (identified by its public key and private key) to another wallet
    (identified by its public key).

    Parameters
    ----------
    addr_from : str
        The public key (wallet address) of the sender's wallet.
    private_key : str
        The private key of the sender's wallet used for signing
        the transaction.
    addr_to : str
        The public key (wallet address) of the recipient's wallet.
    amount : str
        The amount of coins to send to the recipient.

    Returns
    -------
    None

    Notes
    -----
    The function validates the sender's private key, signs the
    transaction message, and sends the transaction to the
    blockchain node for processing.

    If the private key is invalid or the transaction fails, an
    error message is displayed.

    Make sure that the blockchain node is running and accessible
    for this function to work correctly.
    """
    if len(private_key) == 64:
        signature, message = sign_ECDSA_msg(private_key)
        url = 'http://localhost:5000/txion'
        payload = {"from": addr_from,
                   "to": addr_to,
                   "amount": amount,
                   "signature": signature.decode(),
                   "message": message}
        headers = {"Content-Type": "application/json"}
        res = requests.post(url, json=payload, headers=headers)
        print(res.text)
    else:
        print("Wrong address or key length! Verify and try again.")

def check_transactions():
    """
    Check and display blockchain transactions.

    This function retrieves and displays the list of blockchain
    transactions from the local blockchain node.

    Returns
    -------
    None

    Notes
    -----
    The function sends a request to the blockchain node running at
    'http://localhost:5000/blocks' and displays the retrieved
    transactions in a structured format.

    If a connection error occurs, it prompts the user to ensure
    that the blockchain node is running in another terminal.
    """
    try:
        res = requests.get('http://localhost:5000/blocks')
        parsed = json.loads(res.text)
        print(json.dumps(parsed, indent=4, sort_keys=True))
    except requests.ConnectionError:
        print('Connection error. Make sure that you have run miner.py in another terminal.')

def generate_ECDSA_keys():
    """
    Generate a new wallet with ECDSA key pair.

    This function generates a new wallet by creating a new ECDSA
    key pair, consisting of a private key and a public key (wallet
    address). It saves this information to a text file.

    Returns
    -------
    None

    Notes
    -----
    The function uses the `ecdsa` library to generate a new ECDSA
    key pair. It then prompts the user to provide a name for the
    new wallet address and saves the private key and wallet address
    to a text file.

    The private key and wallet address are required for
    authorizing transactions.
    """
    sk = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    private_key = sk.to_string().hex()
    vk = sk.get_verifying_key()
    public_key = vk.to_string().hex()
    public_key = base64.b64encode(bytes.fromhex(public_key))
    filename = input("Write the name of your new address: ") + ".txt"
    with open(filename, "w") as f:
        f.write(F"Private key: {private_key}\nWallet address / Public key: {public_key.decode()}")
    print(F"Your new address and private key are now in the file {filename}")

def sign_ECDSA_msg(private_key):
    """
    Sign a message using an ECDSA private key.

    This function signs a message using an ECDSA private key,
    producing a digital signature.

    Parameters
    ----------
    private_key : str
        The ECDSA private key used for signing.

    Returns
    -------
    signature : bytes
        The digital signature produced.
    message : str
        The message that was signed.

    Notes
    -----
    The function takes a private key as input, generates a message
    based on the current timestamp, signs the message using ECDSA,
    and returns the digital signature along with the message.
    """
    message = str(round(time.time()))
    bmessage = message.encode()
    sk = ecdsa.SigningKey.from_string(bytes.fromhex(private_key), curve=ecdsa.SECP256k1)
    signature = base64.b64encode(sk.sign(bmessage))
    return signature, message

if __name__ == '__main__':
    print("""       =========================================\n
        ASCII BUCKS v1.0.0 - BLOCKCHAIN SYSTEM\n
       =========================================\n\n""")
    wallet()
    input("Press ENTER to exit...")
    
