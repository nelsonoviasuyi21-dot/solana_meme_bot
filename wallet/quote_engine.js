const https = require("https");

const JUPITER_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote";

function getQuote(inputMint, outputMint, amountLamports) {
  return new Promise((resolve, reject) => {
    const url =
      `${JUPITER_QUOTE_URL}?inputMint=${encodeURIComponent(inputMint)}` +
      `&outputMint=${encodeURIComponent(outputMint)}` +
      `&amount=${encodeURIComponent(amountLamports)}` +
      `&slippageBps=100`;

    https.get(url, (res) => {
      let body = "";

      res.on("data", chunk => body += chunk);

      res.on("end", () => {
        try {
          const data = JSON.parse(body);

          if (res.statusCode !== 200) {
            reject(new Error(data.error || `HTTP ${res.statusCode}`));
            return;
          }

          resolve(data);
        } catch (e) {
          reject(new Error("Invalid quote response"));
        }
      });
    }).on("error", reject);
  });
}

async function main() {
  console.log("========================================");
  console.log(" SOLANA QUOTE ENGINE");
  console.log("========================================");
  console.log("MODE:        QUOTE ONLY");
  console.log("SIGNING:     DISABLED");
  console.log("BROADCAST:   DISABLED");
  console.log("SPEND:       0 SOL");
  console.log("========================================");
  console.log("QUOTE MODULE: READY");
}

main().catch(err => {
  console.error("QUOTE ENGINE ERROR:", err.message);
  process.exit(1);
});
