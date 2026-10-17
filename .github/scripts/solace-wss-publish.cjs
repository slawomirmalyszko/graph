const mqtt = require("mqtt");

const topic = "test/github/actions";
const payload = JSON.stringify({
  source: "github-actions",
  repository: process.env.GITHUB_REPOSITORY,
  run_id: process.env.GITHUB_RUN_ID,
  status: "ok",
});

const client = mqtt.connect(process.env.SOLACE_WSS_URL, {
  username: process.env.SOLACE_USERNAME,
  password: process.env.SOLACE_PASSWORD,
  clientId: `github-actions-${process.env.GITHUB_RUN_ID}`,
  protocolVersion: 4,
  connectTimeout: 15_000,
  reconnectPeriod: 0,
});

const timeout = setTimeout(() => {
  console.error("Timed out while connecting to Solace over WSS");
  client.end(true);
  process.exitCode = 1;
}, 30_000);

client.once("connect", () => {
  client.publish(topic, payload, { qos: 1 }, (error) => {
    clearTimeout(timeout);
    if (error) {
      console.error(`Failed to publish the test event: ${error.message}`);
      process.exitCode = 1;
    } else {
      console.log(`Published a test event to ${topic} over WSS`);
    }
    client.end();
  });
});

client.once("error", (error) => {
  clearTimeout(timeout);
  console.error(`Solace WSS connection failed: ${error.message}`);
  client.end(true);
  process.exitCode = 1;
});
