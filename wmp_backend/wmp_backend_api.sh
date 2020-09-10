export CA_URL="https://tulitahara-ca.southeastasia.cloudapp.azure.com:4443"
export CA_URL_ENROLL_PARTNER_APP="https://tulitahara-ca.southeastasia.cloudapp.azure.com:4443/enroll-partner-app"
export SCBACKEND_URL="https://tulitahara-scbend.southeastasia.cloudapp.azure.com:8449"
export WMPBE_WEBHOOK_SERVICE="https://partner-staging.nuty.in"
export WMP_CHAT_SERVICE_POD="https://partner-staging.nuty.in"
export WMPBE_WEBHOOK_SERVICE_CHAT="wss://partner-staging.nuty.in"
python wmp_backend_api.py websocket

