Create an export via [Slack Export feature](https://artpolis-space.slack.com/services/export). Run it as `python converter.py <folder-with-slack-export> output.jsonl`. It does not support attachments and a lot of bell and whistles. Just basic messages. Note that it is not idempotent as docs suggest. E.g. if it fails after you start loading e.g. users, you then have to not load the users again. 

You have to then:
1. zip it `zip -r data.zip output.jsonl`
2. `EnableLocalMode: true` in your mattermost server config (and restart the server so it takes effect)
3. then run `mmctl import process --bypass-upload data.zip --local`
4. see the results using `mmctl --local import jobs list`

You can add users to channels via:
```
mmctl --local channel users add teamName:channelName user1 user2 user3
```

or delete channels (e.g. if you wanna restart the import):
```
mmctl channel delete teamName:channelName --confirm --local
```

## Notes
1. doesn't export direct messages and private channels