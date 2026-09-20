const fs = require("fs");
const {
  Connection,
  PublicKey,
  Keypair,
  VersionedTransaction,
  clusterApiUrl,
  LAMPORTS_PER_SOL
} = require("@solana/web3.js");
const bs58 = require("bs58");

const CONFIG_FILE = "wallet/config.json";
const SECRET_FILE = "wallet/private_key.secret";

const LIVE_TRADING = false;
const WALLET_PERCENT = 50.0;
const SOL_RESERVE = 0.0;

const RPC_URL = clusterApiUrl("mainnet-beta");
const JUPITER_QUOTE =
  "https://lite-api.jup.ag/swap/v1/quote";
const JUPITER_SWAP =
  "https://lite-api.jup.ag/swap/v1/swap";

async function main() {
  const cfg = JSON.parse(
    fs.readFileSync(CONFIG_FILE, "utf8")
  );

  const wallet = new PublicKey(cfg.wallet_address);

  const secret = fs.readFileSync(
    SECRET_FILE,
    "utf8"
  ).trim();

  const decoded = bs58.default.decode(secret);
  const keypair = Keypair.fromSecretKey(decoded);

  if (
    keypair.publicKey.toBase58() !==
    wallet.toBase58()
  ) {
    throw new Error("PRIVATE KEY / WALLET MISMATCH");
  }

  const connection = new Connection(
    RPC_URL,
    "confirmed"
  );

  const balanceLamports =
    await connection.getBalance(wallet);

  const balanceSol =
    balanceLamports / LAMPORTS_PER_SOL;

  const usableSol =
    Math.max(
      balanceSol - SOL_RESERVE,
      0
    );

  const tradeSol =
    usableSol * (WALLET_PERCENT / 100);

  const tradeLamports =
    Math.floor(
      tradeSol * LAMPORTS_PER_SOL
    );

  console.log("========================================");
  console.log(" SOLANA SWAP EXECUTOR");
  console.log("========================================");
  console.log("RPC:                 CONNECTED");
  console.log("WALLET:              VALID");
  console.log(
    "BALANCE:             " +
    balanceSol.toFixed(6) +
    " SOL"
  );
  console.log(
    "WALLET ALLOCATION:   " +
    WALLET_PERCENT.toFixed(1) +
    "%"
  );
  console.log(
    "TRADE SIZE:          " +
    tradeSol.toFixed(6) +
    " SOL"
  );
  console.log(
    "TRADE LAMPORTS:      " +
    tradeLamports
  );
  console.log(
    "LIVE TRADING:        " +
    (LIVE_TRADING ? "ON" : "OFF")
  );
  console.log("SIGNING:             DISABLED");
  console.log("BROADCAST:           DISABLED");
  console.log("========================================");

  if (tradeLamports <= 0) {
    throw new Error(
      "Calculated trade amount is zero"
    );
  }

  const inputMint =
    "So11111111111111111111111111111111111111112";

  const outputMint =
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

  const quoteUrl =
    JUPITER_QUOTE +
    "?inputMint=" +
    inputMint +
    "&outputMint=" +
    outputMint +
    "&amount=" +
    tradeLamports +
    "&slippageBps=100";

  const quoteResponse =
    await fetch(quoteUrl);

  if (!quoteResponse.ok) {
    throw new Error(
      "Jupiter quote HTTP " +
      quoteResponse.status
    );
  }

  const quote = await quoteResponse.json();

  console.log(
    "QUOTE RECEIVED:      YES"
  );

  const swapResponse =
    await fetch(
      JUPITER_SWAP,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          quoteResponse: quote,
          userPublicKey:
            wallet.toBase58(),
          wrapAndUnwrapSol: true,
          dynamicComputeUnitLimit: true
        })
      }
    );

  if (!swapResponse.ok) {
    const text =
      await swapResponse.text();

    throw new Error(
      "Jupiter swap HTTP " +
      swapResponse.status +
      ": " +
      text
    );
  }

  const swap =
    await swapResponse.json();

  if (!swap.swapTransaction) {
    throw new Error(
      "No swap transaction returned"
    );
  }

  console.log(
    "UNSIGNED TRANSACTION: RECEIVED"
  );
  console.log(
    "SIGNING:             DISABLED"
  );
  console.log(
    "BROADCAST:           DISABLED"
  );
  console.log(
    "TRANSACTION SENT:    NO"
  );
  console.log("========================================");
}

main().catch((err) => {
  console.error(
    "EXECUTOR ERROR:",
    err.message
  );
  process.exit(1);
});
