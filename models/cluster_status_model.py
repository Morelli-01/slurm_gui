from typing import Dict, List, Optional, Tuple, Any
from PyQt6.QtCore import QObject, pyqtSignal
from modules.defaults import *
from utils import parse_memory_size

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
            max_gpu_count = max(int(node_info.get("total_gres/gpu", 0)), max_gpu_count)
        
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
        state = node_info.get("State", "").upper()
        total_gpus = int(node_info.get("total_gres/gpu", 0))
        used_gpus = int(node_info.get("alloc_gres/gpu", 0))
        reserved = node_info.get("RESERVED", "NO").upper() == "YES"
        
        # Calculate student vs production GPU usage
        stud_used, prod_used = self._calculate_gpu_usage_breakdown(node_info, used_gpus)
        
        # Determine block states for GPUs
        block_states = self._determine_block_states(
            node_info, state, total_gpus, used_gpus, stud_used, prod_used, reserved
        )
        
        # Get job information for tooltips
        node_jobs = self._get_node_jobs(node_info["NodeName"])
        tooltips = self._generate_gpu_tooltips(node_jobs, stud_used, total_gpus)
        
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
    
    def _calculate_gpu_usage_breakdown(self, node_info: Dict[str, Any], used_gpus: int) -> Tuple[int, int]:
        """Calculate breakdown of GPU usage between students and production"""
        filtered_jobs = [job for job in self._jobs_data if node_info["NodeName"] == job.get("Nodelist", "")]
        stud_used = 0
        prod_used = 0
        
        for job in filtered_jobs:
            if isinstance(job.get("Account"), str):
                try:
                    job_gpus = int(job.get("GPUs", 0))
                except ValueError:
                    continue
                    
                # Check if it's a student job
                is_student_job = any(k in job["Account"] for k in STUDENTS_JOBS_KEYWORD)
                
                if is_student_job:
                    stud_used += job_gpus
                else:
                    prod_used += job_gpus
        
        # Ensure counts don't exceed used_gpus
        stud_used = min(stud_used, used_gpus)
        prod_used = used_gpus - stud_used
        
        return stud_used, prod_used
    
    def _determine_block_states(self, node_info: Dict[str, Any], state: str, total_gpus: int, 
                               used_gpus: int, stud_used: int, prod_used: int, reserved: bool) -> List[str]:
        """Determine the state of each GPU block for visualization"""
        if reserved:
            return ["reserved"] * total_gpus
        
        if "DRAIN" in state or "DOWN" in state or "UNKNOWN" in state:
            return ["unavailable"] * total_gpus
        
        if "NOT_RESPONDING" in state:
            return ["unavailable"] * total_gpus
        
        # For allocated/mixed states, determine constraint levels
        high_constraint_state = False
        mid_constraint_state = False
        
        if "ALLOCATED" in state or "MIXED" in state:
            try:
                total_cpu = int(node_info.get("total_cpu", 1))
                alloc_cpu = int(node_info.get("alloc_cpu", 0))
                total_mem = parse_memory_size(node_info.get("total_mem", "1M")) // 1024**3
                alloc_mem = parse_memory_size(node_info.get("alloc_mem", "0M")) // 1024**3
                
                cpu_utilization = alloc_cpu / total_cpu if total_cpu > 0 else 0
                mem_utilization = alloc_mem / total_mem if total_mem > 0 else 0
                
                high_constraint_state = cpu_utilization >= 0.9 or mem_utilization >= 0.9
                mid_constraint_state = (cpu_utilization >= 0.7 or mem_utilization >= 0.7) and not high_constraint_state
                
            except (ValueError, IndexError):
                high_constraint_state = False
                mid_constraint_state = False
        
        # Build block states
        current_blocks = []
        current_blocks.extend(["stud_used"] * stud_used)
        current_blocks.extend(["prod_used"] * prod_used)
        
        remaining_gpus = total_gpus - used_gpus
        if remaining_gpus > 0:
            if "ALLOCATED" in state or "MIXED" in state:
                if high_constraint_state:
                    current_blocks.extend(["high-constraint"] * remaining_gpus)
                elif mid_constraint_state:
                    current_blocks.extend(["mid-constraint"] * remaining_gpus)
                else:
                    current_blocks.extend(["available"] * remaining_gpus)
            else:
                current_blocks.extend(["available"] * remaining_gpus)
        
        return current_blocks
    
    def _get_node_jobs(self, node_name: str) -> List[Dict[str, Any]]:
        """Get all jobs running on a specific node"""
        return [job for job in self._jobs_data if node_name == job.get("Nodelist", "")]
    
    def _generate_gpu_tooltips(self, node_jobs: List[Dict[str, Any]], stud_used: int, total_gpus: int) -> List[str]:
        """Generate tooltips for GPU blocks showing job users"""
        tooltips = [""] * total_gpus
        
        # Separate student and production jobs
        stud_jobs = []
        prod_jobs = []
        for job in node_jobs:
            account = job.get("Account", "")
            if any(k in account for k in STUDENTS_JOBS_KEYWORD):
                stud_jobs.append(job)
            else:
                prod_jobs.append(job)
        
        # Map tooltips for student jobs
        current_gpu_index = 0
        for job in stud_jobs:
            num_gpus = int(job.get("GPUs", 0))
            user = job.get("User", "unknown")
            for i in range(num_gpus):
                if current_gpu_index + i < len(tooltips):
                    tooltips[current_gpu_index + i] = user
            current_gpu_index += num_gpus
        
        # Map tooltips for production jobs
        for job in prod_jobs:
            num_gpus = int(job.get("GPUs", 0))
            user = job.get("User", "unknown")
            for i in range(num_gpus):
                if current_gpu_index + i < len(tooltips):
                    tooltips[current_gpu_index + i] = user
            current_gpu_index += num_gpus
        
        return tooltips
    
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
            
            total_cpu = int(node_info.get("total_cpu", 1))
            alloc_cpu = int(node_info.get("alloc_cpu", 0))
            cpu_usage_percent = (alloc_cpu / total_cpu * 100) if total_cpu > 0 else 0
            
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
            
            try:
                total_mem_mb = parse_memory_size(node_info.get("total_mem", "1M"))
                alloc_mem_mb = parse_memory_size(node_info.get("alloc_mem", "0M"))
            except (ValueError, IndexError):
                total_mem_mb = 1
                alloc_mem_mb = 0
            
            ram_usage_percent = (alloc_mem_mb / total_mem_mb * 100) if total_mem_mb > 0 else 0
            
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