const mqtt = require("mqtt");

const topic = `test/github/actions/${process.env.GITHUB_RUN_ID}/${process.env.GITHUB_RUN_ATTEMPT}`;
const payload = JSON.stringify({
  source: "github-actions",
  repository: process.env.GITHUB_REPOSITORY,
  run_id: process.env.GITHUB_RUN_ID,
  attempt: process.env.GITHUB_RUN_ATTEMPT,
  status: "ok",
});

const connectionOptions = (role) => ({
  username: process.env.SOLACE_USERNAME,
  password: process.env.SOLACE_PASSWORD,
  clientId: `github-actions-${role}-${process.env.GITHUB_RUN_ID}-${process.env.GITHUB_RUN_ATTEMPT}`,
  protocolVersion: 4,
  connectTimeout: 15_000,
  reconnectPeriod: 0,
});

let subscriber;
let publisher;
let publishAcknowledged = false;
let matchingMessageReceived = false;
let finished = false;

function closeClients(force = false) {
  subscriber?.end(force);
  publisher?.end(force);
}

function fail(message) {
  if (finished) return;
  finished = true;
  clearTimeout(timeout);
  console.error(`[failure] ${message}`);
  closeClients(true);
  process.exitCode = 1;
}

function finishIfComplete() {
  if (finished || !publishAcknowledged || !matchingMessageReceived) return;
  finished = true;
  clearTimeout(timeout);
  console.log("[verify] Received payload exactly matches the published payload");
  console.log("[success] Solace WSS publish/subscribe round trip completed");

  subscriber.unsubscribe(topic, (error) => {
    if (error) {
      console.warn(`[subscriber] Unsubscribe warning: ${error.message}`);
    } else {
      console.log(`[subscriber] Unsubscribed from ${topic}`);
    }
    subscriber.end(false, {}, () => console.log("[subscriber] Disconnected"));
  });
  publisher.end(false, {}, () => console.log("[publisher] Disconnected"));
}

const timeout = setTimeout(() => {
  fail("Timed out waiting for the Solace WSS round trip to complete");
}, 30_000);

console.log("[subscriber] Connecting to Solace over WSS");
subscriber = mqtt.connect(
  process.env.SOLACE_WSS_URL,
  connectionOptions("subscriber"),
);

subscriber.once("error", (error) => {
  fail(`Subscriber connection failed: ${error.message}`);
});

subscriber.once("connect", () => {
  console.log("[subscriber] Connected and authenticated");
  console.log(`[subscriber] Subscribing to ${topic} with QoS 1`);

  subscriber.subscribe(topic, { qos: 1 }, (error, grants) => {
    if (error) {
      fail(`Subscription failed: ${error.message}`);
      return;
    }
    if (!grants?.length || grants.some((grant) => grant.qos === 128)) {
      fail(`Broker rejected the subscription to ${topic}`);
      return;
    }

    console.log(`[subscriber] Subscription active on ${topic}`);
    console.log("[publisher] Connecting to Solace over WSS");
    publisher = mqtt.connect(
      process.env.SOLACE_WSS_URL,
      connectionOptions("publisher"),
    );

    publisher.once("error", (publisherError) => {
      fail(`Publisher connection failed: ${publisherError.message}`);
    });

    publisher.once("connect", () => {
      console.log("[publisher] Connected and authenticated");
      console.log(`[publisher] Publishing test event to ${topic} with QoS 1`);

      publisher.publish(topic, payload, { qos: 1 }, (publishError) => {
        if (publishError) {
          fail(`Publish failed: ${publishError.message}`);
          return;
        }
        publishAcknowledged = true;
        console.log("[publisher] Broker acknowledged the published message");
        finishIfComplete();
      });
    });
  });
});

subscriber.on("message", (receivedTopic, receivedPayload) => {
  if (finished || receivedTopic !== topic) return;

  console.log(`[subscriber] Message received from ${receivedTopic}`);
  const actual = receivedPayload.toString("utf8");
  if (actual !== payload) {
    fail(`Payload mismatch\nExpected: ${payload}\nActual:   ${actual}`);
    return;
  }

  matchingMessageReceived = true;
  console.log("[subscriber] Received the expected test payload");
  finishIfComplete();
});
