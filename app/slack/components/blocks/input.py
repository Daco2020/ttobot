# {
#     "type": "input",
#     "block_id": "content_url",
#     "element": {
#         "type": "url_text_input",
#         "action_id": "url_text_input-action",
#     },
#     "label": {
#         "type": "plain_text",
#         "text": "글 링크",
#         "emoji": True,
#     },
# },


# class InputBlock:
#     def __init__(
#         self,
#         block_id: str,
#         label: str,
#         action_id: str = "",
#         placeholder: str = "",
#         initial_value: str = "",
#         is_optional: bool = False,
#         is_emoji: bool = False,
#     ):
#         self.block_id = block_id
#         self.label = label
#         self.action_id = action_id
#         self.placeholder = placeholder
#         self.initial_value = initial_value
#         self.is_optional = is_optional
#         self.is_emoji = is_emoji

#     def render(self):
#         return {
#             "type": "input",
#             "block_id": self.block_id,
#             "element": {
#                 "type": "plain_text_input",
#                 "action_id": self.action_id,
#                 "initial_value": self.initial_value,
#             },
#             "label": {
#                 "type": "plain_text",
#                 "text": self.label,
#                 "emoji": self.is_emoji,
#             },
#             "optional": self.is_optional,
#         }

#                     {
#                         "type": "input",
#                         "block_id": "author_search",
#                         "optional": True,
#                         "element": {
#                             "type": "plain_text_input",
#                             "action_id": "author_name",
#                             "placeholder": {
#                                 "type": "plain_text",
#                                 "text": "이름을 입력해주세요.",
#                             },
#                             "multiline": False,
#                         },
#                         "label": {
#                             "type": "plain_text",
#                             "text": "글 작성자",
#                             "emoji": False,
#                         },
#                     },
# class Block:

#     @staticmethod
#     def input(
#         block_id: str,
#         label: str,
#         action_id: str,
#         placeholder: str,
#         initial_value: str = "",
#         is_optional: bool = False,
#         is_emoji: bool = False,
#     ):
#         return InputBlock(
#             block_id,
#             label,
#             action_id,
#             placeholder,
#             initial_value,
#             is_optional,
#             is_emoji,
#         ).render()


# Block.input()


# class Modal:
#     def __init__(
#         self,
#         title: str,
#         blocks: list[Block],
#         submit: str = "Submit",
#         close: str = "Cancel",
#     ):
#         self.title = title
#         self.blocks = blocks
#         self.submit = submit
#         self.close = close

#     def block(self, block: Block):
#         self.blocks.append(block)

#     def render(self):
#         return {
#             "type": "modal",
#             "title": {
#                 "type": "plain_text",
#                 "text": self.title,
#                 "emoji": True,
#             },
#             "blocks": self.blocks,
#             "submit": {
#                 "type": "plain_text",
#                 "text": self.submit,
#                 "emoji": True,
#             },
#             "close": {
#                 "type": "plain_text",
#                 "text": self.close,
#                 "emoji": True,
#             },
#         }

# modal = Modal("title", [Block.input()]).render()
