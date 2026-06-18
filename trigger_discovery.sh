#!/bin/bash
while true; do
  STATUS=$(gcloud builds describe 536ad2c3-b5fb-4fcb-af71-049771837bb0 --format="value(status)")
  if [ "$STATUS" = "SUCCESS" ]; then
    echo "Build succeeded. Triggering pipeline."
    gcloud beta run jobs execute discovery-pipeline --region=us-central1 --args="--field","Alien Mathematics","--budget-usd","200"
    break
  elif [ "$STATUS" = "WORKING" ] || [ "$STATUS" = "QUEUED" ]; then
    echo "Still building..."
    sleep 10
  else
    echo "Build failed with status $STATUS"
    break
  fi
done
