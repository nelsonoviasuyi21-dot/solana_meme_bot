const https = require("https");
const fs = require("fs");
const bs58 = require("bs58");
const { Keypair } = require("@solana/web3.js");

const SOL = "So11111111111111111111111111111111111111112";
const USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const AMOUNT = "1000000";

function request(method, url, body = null) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;

    const req = https.request(url, {
      method,
      headers: data
        ? {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(data)
          }
        : {}
    }, res => {
      let out = "";
      res.on("data", chunk => out += chunk);
      res.on("end", () => {
        try {
          resolve({
            status: res.statusCode,
            data: JSON.parse(out)
          });
        } catch {
          reject(new Error("Invalid JSON response"));
        }
      });
    });

    req.on("error", reject);

    if (data) req.write(data);
    req.end();
  });
}

async function main() {
  const key = fs.readFileSync("wallet/private_key.secret", "utf8").trim();
  const kp = Keypair.fromSecretKey(bs58.default.decode(key));

  console.log("========================================");
  console.log(" SOLANA SWAP BUILD TEST");
  console.log("========================================");

  const quoteUrl =
    "https://lite-api.jup.ag/swap/v1/quote" +
    `?inputMint=${SOL}` +
    `&outputMint=${USDC}` +
    `&amount=${AMOUNT}` +
    "&slippageBps=100";

  const quote = await request("GET", quoteUrl);

  console.log("QUOTE HTTP:", quote.status);

  if (quote.status !== 200 || !quote.data.outAmount) {
    throw new Error("Fresh quote was not received");
  }

  console.log("QUOTE RECEIVED: YES");

  const swap = await request(
    "POST",
    "https://lite-api.jup.ag/swap/v1/swap",
    {
      quoteResponse: quote.data,
      userPublicKey: kp.publicKey.toBase58(),
      wrapAndUnwrapSol: true,
      dynamicComputeUnitLimit: true
    }
  );

  console.log("SWAP BUILD HTTP:", swap.status);

  if (swap.status !== 200 || !swap.data.swapTransaction) {
    console.log("UNSIGNED TRANSACTION: NOT RECEIVED");
    console.log(
      "JUPITER MESSAGE:",
      swap.data.error || swap.data.errorMessage || "No transaction returned"
    );
    console.log("SIGNING: DISABLED");
    console.log("BROADCAST: DISABLED");
    return;
  }

  console.log("UNSIGNED TRANSACTION: RECEIVED");
  console.log("SIGNING: DISABLED");
  console.log("BROADCAST: DISABLED");
  console.log("TRANSACTION SENT: NO");
  console.log("========================================");
}

main().catch(err => {
  console.error("BUILD TEST ERROR:", err.message);
  process.exit(1);
});
