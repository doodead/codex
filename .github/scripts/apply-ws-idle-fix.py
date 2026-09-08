from pathlib import Path

path = Path("codex-rs/codex-api/src/endpoint/responses_websocket.rs")
text = path.read_text(encoding="utf-8")

marker = "const WS_HEARTBEAT_INTERVAL: Duration = Duration::from_secs(20);"
if marker in text:
    print("WebSocket liveness patch is already applied.")
    raise SystemExit(0)

old = '''        let pump_task = tokio::spawn(async move {
            let mut inner = inner;
            loop {
                tokio::select! {
                    command = rx_command.recv() => {
'''
new = '''        let pump_task = tokio::spawn(async move {
            let mut inner = inner;
            let mut heartbeat = tokio::time::interval_at(
                Instant::now() + WS_HEARTBEAT_INTERVAL,
                WS_HEARTBEAT_INTERVAL,
            );
            heartbeat.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
            loop {
                tokio::select! {
                    _ = heartbeat.tick() => {
                        if let Err(err) = inner.send(Message::Ping(Default::default())).await {
                            let _ = tx_message.send(Err(err));
                            break;
                        }
                    }
                    command = rx_command.recv() => {
'''
if old not in text:
    raise SystemExit("Could not locate WsStream pump insertion point; upstream changed.")
text = text.replace(old, new, 1)

old = '''                            Ok(Message::Ping(payload)) => {
                                if let Err(err) = inner.send(Message::Pong(payload)).await {
                                    let _ = tx_message.send(Err(err));
                                    break;
                                }
                            }
                            Ok(Message::Pong(_)) => {}
'''
new = '''                            Ok(Message::Ping(payload)) => {
                                let activity = Message::Ping(payload.clone());
                                if let Err(err) = inner.send(Message::Pong(payload)).await {
                                    let _ = tx_message.send(Err(err));
                                    break;
                                }
                                if tx_message.send(Ok(activity)).is_err() {
                                    break;
                                }
                            }
                            Ok(message @ Message::Pong(_)) => {
                                if tx_message.send(Ok(message)).is_err() {
                                    break;
                                }
                            }
'''
if old not in text:
    raise SystemExit("Could not locate Ping/Pong handling; upstream changed.")
text = text.replace(old, new, 1)

old = '''const X_CODEX_TURN_STATE_HEADER: &str = "x-codex-turn-state";
'''
new = '''const WS_HEARTBEAT_INTERVAL: Duration = Duration::from_secs(20);
const X_CODEX_TURN_STATE_HEADER: &str = "x-codex-turn-state";
'''
if old not in text:
    raise SystemExit("Could not locate WebSocket constants; upstream changed.")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8", newline="\n")
print(f"Applied WebSocket liveness patch to {path}")
