import json
import hmac
import secrets

import azure.functions as func
import flask
from azure.messaging.webpubsubservice import WebPubSubServiceClient

app = flask.Flask(__name__)

CONNECTION_STRING = '<<<REDACTED CONNECTION STRING>>>'
HUB = 'myHub1'
TWITCH_SECRET = '<<<REDACTED TWITCH SECRET>>>'

INDEX = """\
<!doctype html>
<html>
<body>
<style>
</style>
<script>
(() => {
  let g = () => {
    let s = new WebSocket(WEBSOCKET_URL);
    s.addEventListener('close', () => setTimeout(g, 100));
    s.addEventListener('error', () => setTimeout(g, 100));
    s.addEventListener('open', () => {
      console.log('connected!')
    });
    s.addEventListener('message', (e) => {
      const data = JSON.parse(e.data);
      let msg = document.createElement('div');
      msg.innerText = `THANKS FOR FOLLOWING ${data.event.user_name}`;
      msg.style.fontSize = '72px';
      document.body.appendChild(msg);
      setTimeout(() => document.body.removeChild(msg), 5000);
    });
  }
  g();
})();
</script>
</body>
</html>
"""


@app.route('/')
def index():
    service = WebPubSubServiceClient.from_connection_string(CONNECTION_STRING, hub=HUB)
    token = service.get_client_access_token()
    return INDEX.replace('WEBSOCKET_URL', json.dumps(token['url']))

# Twitch-Eventsub-Message-Type
# - notification
# - webhook_callback_verification
# - revocation

# Twitch-Eventsub-Message-Signature
# - Twitch-Eventsub-Message-Id
# - Twitch-Eventsub-Message-Timestamp
# - raw request body


@app.route('/twitch-webhook', methods=['POST'])
def twitch_webhook():
    sig = hmac.new(TWITCH_SECRET.encode(), digestmod='sha256')
    sig.update(flask.request.headers['Twitch-Eventsub-Message-Id'].encode())
    sig.update(flask.request.headers['Twitch-Eventsub-Message-Timestamp'].encode())
    sig.update(flask.request.data)
    if not secrets.compare_digest(
        flask.request.headers['Twitch-Eventsub-Message-Signature'],
        f'sha256={sig.hexdigest()}',
    ):
        flask.abort(400, description='invalid signature')

    if flask.request.headers['Twitch-Eventsub-Message-Type'] == 'webhook_callback_verification':
        return flask.request.json['challenge'], 200, {'Content-Type': 'text/plain'}
    elif flask.request.headers['Twitch-Eventsub-Message-Type'] == 'notification':
        service = WebPubSubServiceClient.from_connection_string(CONNECTION_STRING, hub=HUB)
        service.send_to_all(flask.request.json)

    return '', 204, {'Content-Type': 'text/plain'}


@app.route('/send-msg', methods=['POST'])
def send_msg():
    service = WebPubSubServiceClient.from_connection_string(CONNECTION_STRING, hub=HUB)
    service.send_to_all({"data": "hello world"})
    return '', 204


def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    return func.WsgiMiddleware(app.wsgi_app).handle(req, context)
