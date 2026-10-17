const mqtt = require("mqtt");

const topic = `test/github/actions/${process.env.GITHUB_RUN_ID}/${process.env.GITHUB_RUN_ATTEMPT}`;
const payload = JSON.stringify({
  source: "github-actions",
  repository: process.env.GITHUB_REPOSITORY,
  run_id: process.env.GITHUB_RUN_ID,
  attempt: process.env.GITHUB_RUN_ATTEMPT,
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
  console.error("Timed out waiting for the test event from Solace over WSS");
  client.end(true);
  process.exitCode = 1;
}, 30_000);

client.once("connect", () => {
  client.subscribe(topic, { qos: 1 }, (subscribeError) => {
    if (subscribeError) {
      clearTimeout(timeout);
      console.error(`Failed to subscribe to ${topic}: ${subscribeError.message}`);
      client.end(true);
      process.exitCode = 1;
      return;
    }

    client.publish(topic, payload, { qos: 1 }, (publishError) => {
      if (publishError) {
        clearTimeout(timeout);
        console.error(`Failed to publish the test event: ${publishError.message}`);
        client.end(true);
        process.exitCode = 1;
      }
    });
  });
});

client.on("message", (receivedTopic, receivedPayload) => {
  if (receivedTopic !== topic) {
    return;
  }

  clearTimeout(timeout);
  const actual = receivedPayload.toString("utf8");
  if (actual !== payload) {
    console.error("Received test event does not match the published payload");
    console.error(`Expected: ${payload}`);
    console.error(`Actual:   ${actual}`);
    process.exitCode = 1;
  } else {
    console.log(`Published and received matching test event on ${topic} over WSS`);
  }

  client.unsubscribe(topic, (error) => {
    if (error) {
      console.error(`Failed to unsubscribe from ${topic}: ${error.message}`);
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
