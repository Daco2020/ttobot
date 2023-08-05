#!/usr/bin/python3

import re
import sys

COMMIT_MESSAGE_REGEX = (
    r'^((revert: ")?(feat|fix|docs|style|refactor|perf|test|ci|build|chore)'
    r"(\(.*\))?!?:\s.{1,50})"
)


def valid_commit_message(message: str) -> bool:
    """
    Function to validate the commit message
    Args:
        message (str): The message to validate
    Returns:
        bool: True for valid messages, False otherwise
    """
    if not re.match(COMMIT_MESSAGE_REGEX, message):
        print(
            "Proper commit message format is required for automated changelog"
            "generation. Examples:\n\n"
        )
        print("feat(compiler): add 'comments' option")
        print("fix(v-model): handle events on blur (close #28)\n\n")
        print("See COMMIT_CONVENTION from Notion for more details.\n")
        print(
            "You can also use cz commit to interactively "
            "generate a commit message.\n"
        )
        return False

    print("Commit message is valid.")
    return True


def main() -> None:
    """Main function."""
    message_file = sys.argv[1]
    try:
        txt_file = open(message_file, "r")
        commit_message = txt_file.read()
    finally:
        txt_file.close()

    if not valid_commit_message(commit_message):
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
