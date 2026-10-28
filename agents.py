import functools
import os

from google import genai
from google.genai import types

import tools

MODEL = os.environ.get("GENAI_MODEL", "gemini-3.5-flash-lite")

COLOURS = {"Manager": "\033[95m", "Inventory Agent": "\033[96m",
           "Purchasing Agent": "\033[93m"}
RESET, DIM = "\033[0m", "\033[2m"

def log_tool(agent_name: str, func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        shown = ", ".join([repr(a) for a in args] + [f"{k} = {v!r}" for k, v in kwargs.items()])
        colour = COLOURS.get(agent_name, "")
        print(f"{DIM} {colour}{agent_name}{RESET}{DIM} -> {func.__name__}({shown}){RESET}")
        return func(*args, **kwargs)
    return wrapper

class Agent:
    def __init__(self, client: genai.Client, name: str, instructions: str, agent_tools: list):
        self.name = name
        self.chat = client.chats.create(
            model = MODEL,
            config= types.GenerateContentConfig(
                system_instruction=instructions,
                tools=[log_tool(name, t) for t in agent_tools],
                temperature = 0.2,
automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls = 15),
            ),
        )
    def ask(self, message: str):
        response = self.chat.send_message(message)
        return response.text or "(no answer)"

INVENTORY_INSTRUCTIONS = """You are the Inventory Agent for a port warehouse in Kingston, Jamaica.
You answer questions about stock levels, item locations and inbound shipments.
Always use your tools to look up real figures; never guess or invent numbers.
Reply with short, factual answers that include SKUs and quantities.
You cannot place orders. If asked to, say that is the Purchasing Agent's job."""

PURCHASING_INSTRUCTIONS = """You are the Purchasing Agent for a port warehouse in Kingston, Jamaica.
You look up supplier details and create purchase orders.
Rules:
- Only create a purchase order when you have been explicitly asked to order or restock an item.
- Unless told a quantity, order the item's reorder_qty (look it up with get_item_details).
- If an order is refused for being over the spending limit, do not split it into smaller
  orders to get around the limit. Report that it needs human approval.
Reply with the PO number, item, quantity, supplier and total cost in JMD."""

MANAGER_INSTRUCTIONS = """You are the Manager Agent for a port warehouse in Kingston, Jamaica.
You talk to the human warehouse staff. You have two specialist agents:
- the Inventory Agent knows stock levels, locations and inbound shipments;
- the Purchasing Agent knows suppliers, costs and can create purchase orders.
You have no direct access to warehouse data, so delegate to them and combine their answers.
Rules:
- Only ask the Purchasing Agent to create orders when the user clearly asks you to order or
  restock. If the user only asks what is low, recommend orders and ask whether to place them.
- Give clear, concise answers. Use a short list when there are several items.
- Show money in Jamaican dollars (J$)."""


def build_team(client: genai.Client) -> Agent:
    inventory = Agent(client, "Inventory Agent", INVENTORY_INSTRUCTIONS,
                      [tools.search_items, tools.list_low_stock, tools.get_inbound_shipments, tools.get_stock_value])
    purchasing = Agent(client, "Purchasing Agent", PURCHASING_INSTRUCTIONS,
                       [tools.get_item_details, tools.create_purchase_order,
                        tools.list_purchase_orders])

    def ask_inventory_agent(question: str) -> str:
        """Ask the Inventory Agent about stock levels, item locations, low stock or inbound shipments.

        Args:
            question: A clear, self-contained question for the Inventory Agent.

        Returns:
            The Inventory Agent's answer.
        """
        return inventory.ask(question)

    def ask_purchasing_agent(request: str) -> str:
        """Ask the Purchasing Agent about suppliers, costs, or to create or list purchase orders.

        Args:
            request: A clear, self-contained request, including SKUs and quantities when ordering.

        Returns:
            The Purchasing Agent's reply.
        """
        return purchasing.ask(request)

    return Agent(client, "Manager", MANAGER_INSTRUCTIONS,
                 [ask_inventory_agent, ask_purchasing_agent])

