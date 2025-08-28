import os
import yaml
import re
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv('.env.dev')


class ConfigLoader:
    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv('ENV', 'dev')
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = os.path.join(self.project_root, 'config', f'config.{self.environment}.yaml')
        
        if not os.path.isfile(self.config_path):
            raise FileNotFoundError(f"Cannot find config file: {self.config_path}")
    
    def _substitute_env_vars(self, value: Any) -> Any:

        if isinstance(value, str):
            pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
            
            def replace_env_var(match):
                var_name = match.group(1)
                default_value = match.group(2) if match.group(2) is not None else ''
                return os.getenv(var_name, default_value)
            
            return re.sub(pattern, replace_env_var, value)
        elif isinstance(value, dict):
            return {k: self._substitute_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._substitute_env_vars(item) for item in value]
        else:
            return value
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', separator: str = '_') -> Dict[str, Any]:

        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{separator}{k}".upper() if parent_key else k.upper()
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, separator).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def get_dict(self) -> Dict[str, Any]:

        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file)
            
            if not config_data:
                raise ValueError(f"Config file {self.config_path} is empty or invalid")
            
            config_data = self._substitute_env_vars(config_data)
            
            flattened_config = self._flatten_dict(config_data)
            
            return flattened_config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML config file {self.config_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading config: {e}")
    
    def get_nested_dict(self) -> Dict[str, Any]:

        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file)
            
            if not config_data:
                raise ValueError(f"Config file {self.config_path} is empty or invalid")
            
            config_data = self._substitute_env_vars(config_data)
            
            return config_data
            
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML config file {self.config_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading config: {e}")


config_loader = ConfigLoader()
api_config = config_loader.get_dict()

nested_config = config_loader.get_nested_dict()
