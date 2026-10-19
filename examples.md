# Examples

## Get ADE devices that have a certain profile assigned

```sh
token=$(gmac-get-ade-tokens | jq -r '.id')
profile=$(gmac-get-enrollment-profiles $token | jq -r 'select(.displayName=="MacOS Klientdrift - Standardmaskiner | Policy") | .profileId')
gmac-get-ade-devices $token | jq --arg PROFILE $profile 'select(.requestedEnrollmentProfileId==$PROFILE)'
```
