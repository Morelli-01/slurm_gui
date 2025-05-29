import unittest
from unittest.mock import patch, MagicMock
from slurm_connection import SlurmConnection

class TestSlurmConnection(unittest.TestCase):
    def setUp(self):
        self.settings_path = "test_settings.json"
        self.connection = SlurmConnection(self.settings_path)

    def tearDown(self):
        # Clean up any test files
        if os.path.exists(self.settings_path):
            os.remove(self.settings_path)

    @patch('slurm_connection.paramiko.SSHClient')
    def test_connect_success(self, mock_ssh):
        """Test successful connection"""
        mock_ssh.return_value.connect.return_value = None
        result = self.connection.connect()
        self.assertTrue(result)
        mock_ssh.return_value.connect.assert_called_once()

    @patch('slurm_connection.paramiko.SSHClient')
    def test_connect_failure(self, mock_ssh):
        """Test connection failure"""
        mock_ssh.return_value.connect.side_effect = Exception("Connection failed")
        result = self.connection.connect()
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
