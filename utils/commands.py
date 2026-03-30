import json
import os

class SlashCommand:
    def __init__(self, name: str):
        self.name = name
        self.id = self._get_id()

    def _get_id(self) -> str:
        try:
            if os.path.exists("assets/commands.json"):
                with open("assets/commands.json", "r") as f:
                    command_map = json.load(f)
                    
                base_name = self.name.split()[0]
                return command_map.get(base_name, command_map.get(self.name, "0"))
        except Exception:
            pass
        return "0"

    def __str__(self) -> str:
        command_id = self.id
        if command_id == "0":
            return f"`/{self.name}`"
        return f"</{self.name}:{command_id}>"

    def __repr__(self) -> str:
        return self.__str__()
