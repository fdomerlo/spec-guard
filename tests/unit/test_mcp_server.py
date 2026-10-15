import json
import subprocess
import sys
import os
import pytest
from unittest.mock import patch
from scripts.mcp_server import get_next_task, verify_phase_gate, mark_task_completed

# We will mock _sg instead of calling the actual sg.py to test mcp_server's logic
@patch('scripts.mcp_server._sg')
def test_get_next_task(mock_sg):
    mock_sg.return_value = ({"status": "ok", "task": {"id": "1", "desc": "do something"}}, 0)
    result = get_next_task("my-change")
    mock_sg.assert_called_once_with("next-task", "--change", "my-change")
    assert result == {"status": "ok", "task": {"id": "1", "desc": "do something"}}

@patch('scripts.mcp_server._sg')
def test_verify_phase_gate(mock_sg):
    mock_sg.return_value = ({"authorized": True}, 0)
    result = verify_phase_gate("my-change", "plan")
    mock_sg.assert_called_once_with("verify-gate", "--change", "my-change", "--phase", "plan")
    assert result == {"authorized": True}

@patch('scripts.mcp_server._sg')
def test_mark_task_completed(mock_sg):
    mock_sg.return_value = ({"status": "ok"}, 0)
    result = mark_task_completed("my-change", "task-1")
    mock_sg.assert_called_once_with("mark-task", "--change", "my-change", "--task-id", "task-1")
    assert result == {"status": "ok"}

def test_mcp_server_handshake():
    """Test de integración verificando el handshake MCP real por stdio."""
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'mcp_server.py'))
    
    proc = subprocess.Popen(
        [sys.executable, script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        def send(msg):
            proc.stdin.write(json.dumps(msg) + '\n')
            proc.stdin.flush()
            
        send({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {'name': 'test', 'version': '0.1'}
            }
        })
        
        # Leemos la respuesta a initialize
        resp_init = json.loads(proc.stdout.readline().strip())
        assert resp_init['id'] == 1
        assert resp_init['jsonrpc'] == '2.0'
        
        send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        
        send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})
        resp_tools = json.loads(proc.stdout.readline().strip())
        
        assert resp_tools['id'] == 2
        tools = resp_tools['result']['tools']
        assert len(tools) == 5
        
        tool_names = {t['name'] for t in tools}
        assert tool_names == {'get_next_task', 'verify_phase_gate', 'mark_task_completed', 'validate_spec', 'get_rf_status'}
        
    finally:
        proc.terminate()
        proc.wait(timeout=2)
