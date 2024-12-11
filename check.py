import json

path = "files.json"

total_files = 0
discrepancies = 0

with open(path, "r") as f:
    files = json.load(f)
    
    for commit in files:
        commit_sha = commit["commit_sha"]
        
        for content in commit["commit_files"]:
            loc_added = content["loc_added"]
            loc_deleted = content["loc_removed"]
            calculated_loc_added = content["calculated_loc_added"]
            calculated_loc_removed = content["calculated_loc_removed"]
            calculated_loc_changed = content["calculated_loc_changed"]
            
            loc_added = int(loc_added) - int(calculated_loc_changed)
            loc_deleted = int(loc_deleted) - int(calculated_loc_changed)
            
            if loc_added != calculated_loc_added or loc_deleted != calculated_loc_removed:
                discrepancies += 1
                print(f"Discrepancy found in commit {commit_sha}")
                print(f"Expected loc_added: {loc_added}, Actual loc_added: {calculated_loc_added}")
                print(f"Expected loc_deleted: {loc_deleted}, Actual loc_deleted: {calculated_loc_removed}")
                print()
            total_files += 1

print(f"Total files: {total_files}")
print(f"Total discrepancies: {discrepancies}")