const fs = require("fs");
const {
  Connection,
  PublicKey,
  clusterApiUrl,
  LAMPORTS_PER_SOL
} = require("@solana/web3.js");

const CONFIG = "wallet/config.json";
const DRY_RUN = true;

async function main() {
  const cfg = JSON.parse(fs.readFileSync(CONFIG, "utf8"));
  const wallet = new PublicKey(cfg.wallet_address);

  const connection = new Connection(
    clusterApiUrl("mainnet-beta"),
    "confirmed"
  );

  const balance = await connection.getBalance(wallet);
  const sol = balance / LAMPORTS_PER_SOL;

  console.log("========================================");
  console.log(" SOLANA TRADE ENGINE - DRY RUN");
  console.log("========================================");
  console.log("RPC:              CONNECTED");
  console.log("WALLET:           VALID");
  console.log("BALANCE:          " + sol.toFixed(6) + " SOL");
  console.log("MODE:              DRY RUN");
  console.log("SIGNING:           DISABLED");
  console.log("BROADCAST:         DISABLED");
  console.log("TRANSACTION SENT:  NO");
  console.log("========================================");
}

main().catch(err => {
  console.error("TRADE ENGINE ERROR:", err.message);
  process.exit(1);
});
