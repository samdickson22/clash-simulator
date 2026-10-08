# Collector startup race

At 05:08:57 UTC the first collector found no confirmation directory because the node supervisor was still importing its runtime. It exited 1, with evidence retained in s3-collect-r1.log/.exit and INCIDENT-collector-startup-r1.json. Both hosts were reachable and running 76 workers each. Both receipt directories were then verified to exist. The unchanged collector restarted as s3-collect-r1b, still reading worker attempt r1. No game reruns, code changes or outcome access occurred.
