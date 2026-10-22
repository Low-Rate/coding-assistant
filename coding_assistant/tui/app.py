"""Main TUI application using Textual."""

from typing import Any
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, Tree, Label, ListView, ListItem
from textual.widgets import RichLog, MarkdownViewer
from textual.screen import Screen
from textual.message import Message
from textual.reactive import reactive

from coding_assistant.tui.panels.chat import ChatPanel
from coding_assistant.tui.panels.file_tree import FileTreePanel
from coding_assistant.tui.panels.diff import DiffPanel
from coding_assistant.tui.panels.status import StatusPanel
from coding_assistant.agent.session import SessionManager, Session
from coding_assistant.agent.prompt_builder import PromptContext
from coding_assistant.config.settings import get_settings


class CodingAssistantApp(App):
    """Main TUI application for the coding assistant."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
        layout: horizontal;
    }

    #left-panel {
        width: 30%;
        border-right: solid $primary;
    }

    #right-panel {
        width: 70%;
        layout: vertical;
    }

    #chat-panel {
        height: 70%;
        border-bottom: solid $primary;
    }

    #diff-panel {
        height: 30%;
        display: none;
    }

    #diff-panel.visible {
        display: block;
    }

    #input-area {
        height: auto;
        min-height: 3;
        border-top: solid $primary;
        padding: 1;
    }

    .panel-title {
        text-style: bold;
        padding: 0 1;
        height: 1;
        background: $surface;
        border-bottom: solid $primary;
    }

    Tree {
        padding: 0 1;
    }

    RichLog {
        padding: 1;
    }

    Input {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("ctrl+d", "toggle_diff", "Toggle Diff"),
        Binding("ctrl+f", "focus_files", "Files"),
        Binding("ctrl+i", "focus_input", "Input"),
        Binding("ctrl+/", "command_palette", "Commands"),
        Binding("enter", "send_message", "Send", show=False),
    ]

    TITLE = "Coding Assistant"
    SUB_TITLE = "Local AI coding assistant"

    def __init__(self, project_root: str, session: Session | None = None):
        super().__init__()
        self.project_root = project_root
        self.session = session
        self.session_manager = SessionManager()
        self.settings = get_settings()
        self.agent_loop = None
        self._diff_visible = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            # Left panel - File tree
            with Vertical(id="left-panel"):
                yield Label("📁 Files", classes="panel-title")
                yield FileTreePanel(self.project_root, id="file-tree")

            # Right panel - Chat + Diff + Input
            with Vertical(id="right-panel"):
                with Vertical(id="chat-panel"):
                    yield Label("💬 Chat", classes="panel-title")
                    yield ChatPanel(id="chat")

                with Vertical(id="diff-panel") as diff_panel:
                    yield Label("📝 Diff", classes="panel-title")
                    yield DiffPanel(id="diff")
                    self.diff_panel = diff_panel

                yield Input(
                    placeholder="Type your message... (Enter to send, Ctrl+Enter for newline)",
                    id="input-area",
                )

        yield StatusPanel(id="status")
        yield Footer()

    @property
    def diff_log(self):
        """Access the diff panel's log widget."""
        diff = self.query_one("#diff", DiffPanel)
        return diff._diff_log

    async def on_mount(self) -> None:
        """Initialize on mount."""
        # Load or create session
        if not self.session:
            self.session = self.session_manager.create_session(self.project_root)
        self.session_manager.save_session(self.session)

        # Initialize agent context
        self.context = PromptContext(
            project_root=self.project_root,
            working_dir=self.session.working_dir,
            active_files=self.session.active_files,
            conversation_history=[
                {"role": m.role, "content": m.content, "tool_calls": m.tool_calls}
                for m in self.session.messages
            ],
        )

        # Initialize status panel with backend/model info
        status = self.query_one("#status", StatusPanel)
        status.set_backend(self.settings.llm_backend)
        if self.settings.llm_backend == "litellm":
            status.set_model(self.settings.litellm.default_model)
        else:
            status.set_model(self.settings.ollama.default_model)

        # Focus input
        self.query_one("#input-area", Input).focus()

        # Show welcome message
        chat = self.query_one("#chat", ChatPanel)
        backend_label = "LiteLLM" if self.settings.llm_backend == "litellm" else "Ollama"
        model_name = self.settings.litellm.default_model if self.settings.llm_backend == "litellm" else self.settings.ollama.default_model
        chat.add_system_message(
            f"Welcome to Coding Assistant!\n"
            f"Project: {self.project_root}\n"
            f"Backend: {backend_label}\n"
            f"Model: {model_name}\n"
            f"Press Ctrl+/ for commands, Ctrl+Q to quit."
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message input."""
        message = event.value.strip()
        if not message:
            return

        event.input.value = ""
        await self.send_user_message(message)

    async def send_user_message(self, message: str) -> None:
        """Send user message to agent."""
        chat = self.query_one("#chat", ChatPanel)
        chat.add_user_message(message)

        status = self.query_one("#status", StatusPanel)
        status.set_status("thinking")

        # Run agent loop
        from coding_assistant.agent.loop import AgentLoop

        self.agent_loop = AgentLoop(
            self.context,
            confirm_callback=self.confirm_tool,
        )

        async for event in self.agent_loop.run(message):
            await self.handle_agent_event(event)

        status.set_status("ready")

    async def handle_agent_event(self, event: dict[str, Any]) -> None:
        """Handle events from agent loop."""
        chat = self.query_one("#chat", ChatPanel)
        status = self.query_one("#status", StatusPanel)
        diff = self.query_one("#diff", DiffPanel)

        etype = event.get("type")

        if etype == "turn_start":
            status.set_status(f"turn_{event['turn']}")

        elif etype == "content":
            chat.append_assistant_content(event["content"])

        elif etype == "tool_calls":
            for tool_name in event["calls"]:
                chat.add_tool_call(tool_name)

        elif etype == "tool_result":
            result = event["result"]
            chat.add_tool_result(result.tool_call.name, result.result)
            if result.result.success and "diff" in result.result.metadata:
                diff.show_diff(result.result.metadata["diff"])
                self.show_diff_panel()

        elif etype == "usage":
            status.update_tokens(event["metadata"])

        elif etype == "turn_end":
            pass

        elif etype == "done":
            # Save session
            self.session_manager.save_session(self.session)

    async def confirm_tool(self, tool_call) -> bool:
        """Show confirmation dialog for tool execution."""
        from textual.dialog import Dialog
        from textual.containers import Vertical
        from textual.widgets import Button

        class ConfirmDialog(Dialog[bool]):
            def compose(self) -> ComposeResult:
                yield Vertical(
                    Label(f"Confirm tool execution?"),
                    Label(f"Tool: {tool_call.name}"),
                    Label(f"Args: {tool_call.arguments}"),
                    Button("Confirm", variant="primary", id="confirm"),
                    Button("Cancel", variant="error", id="cancel"),
                )

            def on_button_pressed(self, event: Button.Pressed) -> None:
                self.dismiss(event.button.id == "confirm")

        dialog = ConfirmDialog()
        return await self.push_screen_wait(dialog)

    def action_toggle_diff(self) -> None:
        """Toggle diff panel visibility."""
        self._diff_visible = not self._diff_visible
        diff_panel = self.query_one("#diff-panel")
        diff_panel.set_class(self._diff_visible, "visible")

    def action_focus_files(self) -> None:
        """Focus file tree."""
        self.query_one("#file-tree", FileTreePanel).focus()

    def action_focus_input(self) -> None:
        """Focus input area."""
        self.query_one("#input-area", Input).focus()

    def action_command_palette(self) -> None:
        """Show command palette."""
        self.push_screen(CommandPalette())

    def show_diff_panel(self) -> None:
        """Show the diff panel."""
        self._diff_visible = True
        diff_panel = self.query_one("#diff-panel")
        diff_panel.set_class(True, "visible")


class CommandPalette(Screen):
    """Command palette for quick actions."""

    CSS = """
    CommandPalette {
        align: center middle;
        background: $surface 80%;
    }

    #palette {
        width: 60;
        max-height: 30;
        border: solid $primary;
        background: $surface;
    }

    #palette Label {
        padding: 1 2;
        text-style: bold;
        border-bottom: solid $primary;
    }

    #palette ListView {
        padding: 0;
    }

    #palette ListItem {
        padding: 0 2;
    }

    #palette ListItem:hover {
        background: $primary;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="palette"):
            yield Label("⌘ Command Palette")
            yield ListView(
                ListItem(Label("🔄 Reload Project"), id="reload"),
                ListItem(Label("📁 Open File"), id="open"),
                ListItem(Label("🔍 Search"), id="search"),
                ListItem(Label("🤖 Switch Model"), id="model"),
                ListItem(Label("⚙️ Settings"), id="settings"),
                ListItem(Label("❓ Help"), id="help"),
                id="commands",
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle command selection."""
        command_id = event.item.id
        self.dismiss(command_id)

    def on_key(self, event) -> None:
        """Close on escape."""
        if event.key == "escape":
            self.dismiss(None)