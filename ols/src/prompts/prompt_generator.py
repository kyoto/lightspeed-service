"""Prompt generator based on model / context."""

from copy import copy

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
    SystemMessagePromptTemplate,
)

from ols.constants import ModelFamily

from .prompts import (
    AGENT_SYSTEM_INSTRUCTION,
    QUERY_SYSTEM_INSTRUCTION,
    USE_CONTEXT_INSTRUCTION,
    USE_HISTORY_INSTRUCTION,
)


def restructure_rag_context_pre(text: str, model: str) -> str:
    """Restructure rag text - pre truncation."""
    if ModelFamily.GRANITE in model:
        return "\n[End]\n[Document]\n" + text
    return "\n\nDocument:\n" + text


def restructure_rag_context_post(text: str, model: str) -> str:
    """Restructure rag text - post truncation."""
    if ModelFamily.GRANITE in model:
        return text.removeprefix("\n[End]") + "\n[End]"
    return "\n" + text.lstrip("\n") + "\n"


def restructure_history(message: BaseMessage, model: str) -> BaseMessage:
    """Restructure history."""
    if ModelFamily.GRANITE not in model:
        # No processing required here for gpt.
        return message

    new_message = copy(message)
    # Granite specific formatting for history
    if isinstance(message, HumanMessage):
        new_message.content = "\n<|user|>\n" + str(message.content)
    else:
        new_message.content = "\n<|assistant|>\n" + str(message.content)
    return new_message


class GeneratePrompt:
    """Generate prompt dynamically."""

    def __init__(
        self,
        query: str,
        rag_context: list[str] = [],
        history: list[BaseMessage] = [],
        system_instruction: str = QUERY_SYSTEM_INSTRUCTION,
        tool_call: bool = False,
    ):
        """Initialize prompt generator."""
        self._query = query
        self._rag_context = rag_context
        self._history = history
        self._sys_instruction = system_instruction
        self._tool_call = tool_call

    def _generate_prompt_gpt(self) -> tuple[ChatPromptTemplate, dict]:
        """Generate prompt for GPT."""
        prompt_message = []
        sys_intruction = self._sys_instruction.strip() + "\n"
        llm_input_values: dict = {"query": self._query}

        if self._tool_call:
            sys_intruction = sys_intruction + "\n" + AGENT_SYSTEM_INSTRUCTION.strip()

        if len(self._rag_context) > 0:
            llm_input_values["context"] = "".join(self._rag_context)
            sys_intruction = sys_intruction + "\n" + USE_CONTEXT_INSTRUCTION.strip()

        if len(self._history) > 0:
            llm_input_values["chat_history"] = self._history

            sys_intruction = sys_intruction + "\n" + USE_HISTORY_INSTRUCTION.strip()

        if "context" in llm_input_values:
            sys_intruction = sys_intruction + "\n{context}"

        prompt_message.append(SystemMessagePromptTemplate.from_template(sys_intruction))

        if "chat_history" in llm_input_values:
            prompt_message.append(MessagesPlaceholder("chat_history"))

        prompt_message.append(HumanMessagePromptTemplate.from_template("{query}"))
        return ChatPromptTemplate.from_messages(prompt_message), llm_input_values

    def _generate_prompt_granite(self) -> tuple[PromptTemplate, dict]:
        """Generate prompt for Granite."""
        prompt_message = "<|system|>\n" + self._sys_instruction.strip() + "\n"
        llm_input_values = {"query": self._query}

        if len(self._rag_context) > 0:
            llm_input_values["context"] = "".join(self._rag_context)
            prompt_message = prompt_message + "\n" + USE_CONTEXT_INSTRUCTION.strip()

        if len(self._history) > 0:
            prompt_message = prompt_message + "\n" + USE_HISTORY_INSTRUCTION.strip()
            llm_input_values["chat_history"] = ""
            for message in self._history:
                llm_input_values["chat_history"] += str(message.content)

        if "context" in llm_input_values:
            prompt_message = prompt_message + "\n{context}"
        if "chat_history" in llm_input_values:
            prompt_message = prompt_message + "\n{chat_history}"

        prompt_message = prompt_message + "\n<|user|>\n{query}\n<|assistant|>\n"
        return PromptTemplate.from_template(prompt_message), llm_input_values

    def generate_prompt(
        self, model: str
    ) -> tuple[ChatPromptTemplate | PromptTemplate, dict]:
        """Generate prompt."""
        # For tool call, by default openai schema is considered.
        # Depending upon performance other prompt format will be considered.
        if self._tool_call:
            return self._generate_prompt_gpt()

        # TODO: Use provider, instead of model (Ex: granite with vllm uses openai schema)
        if ModelFamily.GRANITE in model:
            return self._generate_prompt_granite()
        return self._generate_prompt_gpt()
