import os
import json

def check_budgets():
    with open('ai/harness.json', 'r') as f:
        harness = json.load(f)
    
    budgets = harness['budgets']
    shared_path = harness['paths']['shared']
    
    print("--- AI Harness Budget Check ---")
    
    # Check core docs
    for doc in ['ARCHITECTURE.md', 'DOMAIN.md', 'CONSTRAINTS.md', 'STANDARDS.md', 'AGENTS.md']:
        path = os.path.join(shared_path, doc)
        if os.path.exists(path):
            size = os.path.getsize(path)
            # Rough estimate: 4 bytes per token for Markdown
            tokens = size // 4 
            limit = budgets['core_doc_max_tokens']
            status = "PASS" if tokens <= limit else "FAIL"
            print(f"{doc}: {tokens}/{limit} tokens - {status}")

    # Check rules
    rules_path = os.path.join(shared_path, 'rules')
    if os.path.exists(rules_path):
        for rule in os.listdir(rules_path):
            path = os.path.join(rules_path, rule)
            size = os.path.getsize(path)
            tokens = size // 4
            limit = budgets['rule_file_max_tokens']
            status = "PASS" if tokens <= limit else "FAIL"
            print(f"Rule {rule}: {tokens}/{limit} tokens - {status}")

if __name__ == "__main__":
    check_budgets()
