import json
import os
import argparse
import re
from datetime import datetime
from typing import Dict, List, Any


def load_json(file_path: str) -> Any:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_jsonl(data: List[Dict[str, Any]], file_path: str) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        for item in data:
            json.dump(item, f)
            f.write("\n")


def process_users(
    users_data: List[Dict[str, Any]], channels_data: List[Dict[str, Any]]
) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    mattermost_users = []
    user_id_to_name = {}

    # Create a set of valid user IDs
    valid_user_ids = {user["id"] for user in users_data}

    user_channels = {user["id"]: [] for user in users_data}
    for channel in channels_data:
        for member in channel.get("members", []):
            if member in valid_user_ids:  # Only add channel if user ID is valid
                user_channels[member].append(channel["name"])

    for user in users_data:
        mattermost_user = {
            "type": "user",
            "user": {
                "username": user["name"],
                "email": user["profile"]["email"],
                "nickname": user["profile"]["display_name"],
                "first_name": user["profile"]["first_name"],
                "last_name": user["profile"]["last_name"],
                "position": user["profile"].get("title", ""),
                "roles": (
                    "system_user"
                    if not user["is_admin"]
                    else "system_user system_admin"
                ),
                "teams": [
                    {
                        "name": "artpolis",
                        "channels": [
                            {"name": channel_name}
                            for channel_name in user_channels[user["id"]]
                        ],
                    }
                ],
            },
        }
        mattermost_users.append(mattermost_user)
        user_id_to_name[user["id"]] = user["name"]

    # Add UNKNOWN user
    unknown_user = {
        "type": "user",
        "user": {
            "username": "unknown",
            "email": "unknown@example.com",
            "nickname": "Unknown User",
            "first_name": "Unknown",
            "last_name": "User",
            "position": "",
            "roles": "system_user",
            "teams": [{"name": "artpolis", "channels": []}],
        },
    }
    mattermost_users.append(unknown_user)
    user_id_to_name["UNKNOWN"] = "unknown"

    return mattermost_users, user_id_to_name


def process_channels(channels_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mattermost_channels = []
    for channel in channels_data:
        mattermost_channel = {
            "type": "channel",
            "channel": {
                "team": "artpolis",
                "name": channel["name"],
                "display_name": channel["name"],
                "type": "O" if not channel.get("is_private", False) else "P",
                "header": channel["topic"]["value"],
                "purpose": channel["purpose"]["value"],
            },
        }
        mattermost_channels.append(mattermost_channel)
    return mattermost_channels


def convert_mentions(text: str, user_id_to_name: Dict[str, str]) -> str:
    def replace_mention(match):
        user_id = match.group(1)
        username = user_id_to_name.get(user_id)
        if username:
            return f"@{username}"
        else:
            return match.group(0)  # Keep the original mention if user not found

    return re.sub(r"<@(U[A-Z0-9]+)>", replace_mention, text)


import json
import os
import argparse
import re
from datetime import datetime
from typing import Dict, List, Any

# ... [previous functions remain unchanged] ...


def process_messages(
    messages_data: List[Dict[str, Any]],
    channel_name: str,
    user_id_to_name: Dict[str, str],
) -> List[Dict[str, Any]]:
    mattermost_posts = []
    thread_replies = {}

    for message in messages_data:
        # Skip messages without a 'type' field or with certain subtypes
        if "type" not in message or message.get("subtype") in [
            "channel_join",
            "channel_leave",
        ]:
            continue

        # Handle file shares and other non-standard message types
        if message["type"] != "message":
            if "file" in message:
                file_info = message["file"]
                text = f"Shared a file: {file_info.get('name', 'Unnamed file')} ({file_info.get('mimetype', 'Unknown type')})"
            else:
                text = f"Performed action: {message['type']}"
        else:
            text = message.get("text", "")

        # Convert mentions in the text
        converted_text = convert_mentions(text, user_id_to_name)

        # Use Slack's original timestamp
        slack_ts = message.get("ts")

        # Get the username, use 'unknown' if not found
        user_id = message.get("user", "UNKNOWN")
        username = user_id_to_name.get(user_id, "unknown")

        mattermost_post = {
            "team": "artpolis",
            "channel": channel_name,
            "user": username,
            "message": converted_text,
            "create_at": int(
                float(slack_ts) * 1000
            ),  # Convert to milliseconds for Mattermost
            "slack_ts": slack_ts,  # Store original Slack timestamp
        }

        # Handle threaded messages
        if "thread_ts" in message and message["thread_ts"] != message.get("ts"):
            # This is a reply in a thread
            thread_ts = message["thread_ts"]
            if thread_ts not in thread_replies:
                thread_replies[thread_ts] = []
            thread_replies[thread_ts].append(mattermost_post)
        else:
            # This is a parent message or a non-threaded message
            mattermost_posts.append({"type": "post", "post": mattermost_post})

    # Add replies to their parent posts
    for post in mattermost_posts:
        slack_ts = post["post"]["slack_ts"]
        if slack_ts in thread_replies:
            post["post"]["replies"] = thread_replies[slack_ts]

    return mattermost_posts


def main():
    parser = argparse.ArgumentParser(
        description="Convert Slack export to Mattermost import format"
    )
    parser.add_argument("input_dir", help="Path to the Slack export directory")
    parser.add_argument("output_file", help="Path to the output JSONL file")
    args = parser.parse_args()

    slack_export_path = args.input_dir
    output_file = args.output_file

    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    users_data = load_json(os.path.join(slack_export_path, "users.json"))
    channels_data = load_json(os.path.join(slack_export_path, "channels.json"))

    mattermost_data = [{"type": "version", "version": 1}]
    mattermost_users, user_id_to_name = process_users(users_data, channels_data)
    mattermost_data.extend(mattermost_users)
    mattermost_data.extend(process_channels(channels_data))

    for channel in channels_data:
        channel_path = os.path.join(slack_export_path, channel["name"])
        if os.path.isdir(channel_path):
            channel_messages = []
            for message_file in os.listdir(channel_path):
                if message_file.endswith(".json"):
                    messages_data = load_json(os.path.join(channel_path, message_file))
                    channel_messages.extend(messages_data)

            mattermost_data.extend(
                process_messages(channel_messages, channel["name"], user_id_to_name)
            )

    save_jsonl(mattermost_data, output_file)
    print(f"Conversion complete. Output saved to {output_file}")


if __name__ == "__main__":
    main()
