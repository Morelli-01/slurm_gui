from typing import Dict, List, Any
from PyQt6.QtCore import QObject, pyqtSignal

# MODEL
class ClusterStatusModel(QObject):
    """Model: Handles cluster data processing and storage"""
    
    # Signals for data changes
    data_updated = pyqtSignal(dict)  # Emits processed data for all tabs
    connection_status_changed = pyqtSignal(bool)  # True if connected, False if error
    
    def __init__(self):
        super().__init__()
        self._nodes_data = []
        self._jobs_data = []
        self._processed_data = {}
        self._is_connected = True
    
    def update_data(self, nodes_data: List[Dict[str, Any]], jobs_data: List[Dict[str, Any]]) -> None:
        """Update model with new cluster data"""
        # Check connection status
        if not nodes_data and hasattr(self.parent(), 'slurm_connection'):
            # Check if we have no data due to connection issues
            if hasattr(self.parent(), 'slurm_connection') and not self.parent().slurm_connection.check_connection():
                self._is_connected = False
                self.connection_status_changed.emit(False)
                return
        
        self._is_connected = True
        self._nodes_data = nodes_data if nodes_data else []
        self._jobs_data = jobs_data if jobs_data else []
        
        # Process data for all tabs
        self._processed_data = {
            'node_status': self._process_node_status_data(),
            'cpu_usage': self._process_cpu_usage_data(), 
            'ram_usage': self._process_ram_usage_data(),
            'is_connected': self._is_connected
        }
        
        # Emit updated data
        self.data_updated.emit(self._processed_data)
        self.connection_status_changed.emit(True)
    
    def _process_node_status_data(self) -> Dict[str, Any]:
        """Process data for node status visualization"""
        if not self._nodes_data:
            return {'nodes': [], 'max_gpu_count': 0}
        
        # Sort nodes data
        sorted_nodes = self._sort_nodes_data(self._nodes_data)
        
        # Calculate max GPU count
        max_gpu_count = 0
        for node_info in sorted_nodes:
            max_gpu_count = max(int(node_info.get("total_gpus", node_info.get("total_gres/gpu", 0))), max_gpu_count)
        
        # Process each node
        processed_nodes = []
        for node_info in sorted_nodes:
            processed_node = self._process_single_node(node_info)
            processed_nodes.append(processed_node)
        
        return {
            'nodes': processed_nodes,
            'max_gpu_count': max_gpu_count
        }
    
    def _process_single_node(self, node_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single node's data for visualization"""
        node_name = node_info.get("NodeName")
        state = str(node_info.get("state", node_info.get("State", ""))).upper()
        total_gpus = int(node_info.get("total_gpus", node_info.get("total_gres/gpu", 0)))
        used_gpus = int(node_info.get("used_gpus", node_info.get("alloc_gres/gpu", 0)))
        reserved = bool(node_info.get("reserved", str(node_info.get("RESERVED", "NO")).upper() == "YES"))

        block_states = node_info.get("block_states", [])
        tooltips = node_info.get("tooltips", [""] * total_gpus)
        
        return {
            'node_name': node_name,
            'state': state,
            'total_gpus': total_gpus,
            'used_gpus': used_gpus,
            'block_states': block_states,
            'tooltips': tooltips,
            'partition': node_info.get("Partitions", ""),
            'reserved': reserved
        }
    
    def _process_cpu_usage_data(self) -> Dict[str, Any]:
        """Process data for CPU usage visualization"""
        if not self._nodes_data:
            return {'nodes': []}
        
        sorted_nodes = self._sort_nodes_data(self._nodes_data)
        processed_nodes = []

        for node_info in sorted_nodes:
            node_name = node_info.get("NodeName")
            if not node_name:
                continue

            total_cpu = int(node_info.get("total_cpu", 0))
            alloc_cpu = int(node_info.get("alloc_cpu", 0))
            cpu_usage_percent = float(node_info.get("cpu_usage_percent", 0.0))

            processed_nodes.append({
                'node_name': node_name,
                'total_cpu': total_cpu,
                'alloc_cpu': alloc_cpu,
                'cpu_usage_percent': cpu_usage_percent,
                'partition': node_info.get("Partitions", "")
            })
        
        return {'nodes': processed_nodes}
    
    def _process_ram_usage_data(self) -> Dict[str, Any]:
        """Process data for RAM usage visualization"""
        if not self._nodes_data:
            return {'nodes': []}
        
        sorted_nodes = self._sort_nodes_data(self._nodes_data)
        processed_nodes = []

        for node_info in sorted_nodes:
            node_name = node_info.get("NodeName")
            if not node_name:
                continue

            total_mem_mb = int(node_info.get("total_mem_mb", 0))
            alloc_mem_mb = int(node_info.get("alloc_mem_mb", 0))
            ram_usage_percent = float(node_info.get("ram_usage_percent", 0.0))

            processed_nodes.append({
                'node_name': node_name,
                'total_mem_mb': total_mem_mb,
                'alloc_mem_mb': alloc_mem_mb,
                'ram_usage_percent': ram_usage_percent,
                'partition': node_info.get("Partitions", "")
            })
        
        return {'nodes': processed_nodes}
    
    def _sort_nodes_data(self, nodes_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort nodes data by partition and memory"""
        # Filter nodes that have Partitions key
        new_nodes_data = []
        for n in nodes_data:
            if "Partitions" in n.keys():
                new_nodes_data.append(n)
        
        if not new_nodes_data:
            return []
        
        def extract_mem_value(node):
            mem_str = node['total_mem']
            if mem_str.endswith('M'):
                return int(mem_str[:-1])
            return int(mem_str)
        
        return sorted(new_nodes_data, key=lambda x: (x['Partitions'], extract_mem_value(x)), reverse=True)
    
    def get_processed_data(self) -> Dict[str, Any]:
        """Get the current processed data"""
        return self._processed_data
    
    def is_connected(self) -> bool:
        """Check if cluster connection is available"""
        return self._is_connected