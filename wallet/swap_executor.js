const fs = require("fs");
const { Connection, PublicKey, clusterApiUrl, LAMPORTS_PER_SOL } = require("@solana/web3.js");

const CONFIG_FILE = "wallet/config.json";
const LIVE_TRADING = false;
const RPC_URL = clusterApiUrl("mainnet-beta");
const JUPITER_QUOTE = "https://lite-api.jup.ag/swap/v1/quote";
const SOL_MINT = "So11111111111111111111111111111111111111112";

function fail(message) { console.error("EXECUTOR ERROR:", message); process.exit(1); }

async function main() {
  if (LIVE_TRADING) fail("Live trading is disabled in this build.");
  const outputMint = String(process.argv[2] || "").trim();
  const tradeSol = Number(process.argv[3]);
  if (!outputMint) fail("Usage: node wallet/swap_executor.js <token_mint> <amount_sol>");
  if (!Number.isFinite(tradeSol) || tradeSol <= 0) fail("Trade amount must be greater than zero.");

  let cfg;
  try { cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, "utf8")); } catch (e) { fail("wallet/config.json could not be read."); }
  let wallet;
  try { wallet = new PublicKey(cfg.wallet_address); } catch (e) { fail("wallet_address is invalid."); }

  const connection = new Connection(RPC_URL, "confirmed");
  const balanceLamports = await connection.getBalance(wallet);
  const balanceSol = balanceLamports / LAMPORTS_PER_SOL;
  if (tradeSol > balanceSol) fail("Requested paper allocation exceeds wallet balance.");
  const tradeLamports = Math.floor(tradeSol * LAMPORTS_PER_SOL);
  if (tradeLamports <= 0) fail("Trade amount is below one lamport.");

  console.log("========================================");
  console.log(" SOLANA PAPER SWAP EXECUTOR");
  console.log("========================================");
  console.log("RPC:                 CONNECTED");
  console.log("WALLET:              VALID");
  console.log("BALANCE:             " + balanceSol.toFixed(6) + " SOL");
  console.log("TRADE SIZE:          " + tradeSol.toFixed(6) + " SOL");
  console.log("TOKEN MINT:          " + outputMint);
  console.log("LIVE TRADING:        OFF");
  console.log("SIGNING:             DISABLED");
  console.log("BROADCAST:           DISABLED");

  const url = JUPITER_QUOTE + "?inputMint=" + encodeURIComponent(SOL_MINT) + "&outputMint=" + encodeURIComponent(outputMint) + "&amount=" + tradeLamports + "&slippageBps=100";
  const response = await fetch(url);
  if (!response.ok) fail("Jupiter quote HTTP " + response.status);
  const quote = await response.json();
  if (!quote || !quote.outAmount) fail("No usable quote returned.");
  console.log("QUOTE RECEIVED:      YES");
  console.log("EXPECTED OUTPUT:     " + quote.outAmount);
  console.log("UNSIGNED SWAP:       PREPARED FOR PAPER TEST");
  console.log("TRANSACTION SENT:    NO");
  console.log("FUNDS MOVED:         NO");
  console.log("========================================");
}

main().catch(err => fail(err.message));
