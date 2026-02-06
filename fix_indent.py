
import os

FILENAME = r"d:\Backtest\Stock vix\vix_fix_dashboard.py"

def fix_file():
    with open(FILENAME, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    
    # Range to indent: From line 411 to 727 (1-based), so index 410 to 726
    # Note: Line numbers might have shifted slightly due to previous edits.
    # We look for specific markers.
    
    start_marker = "report_content = st.session_state['ai_cache'].get(selected_ticker)"
    end_marker = 'st.info("Enter Gemini API Key in Sidebar to enable Auto-Analysis.")'
    
    in_block = False
    start_idx = -1
    end_idx = -1
    
    for i, line in enumerate(lines):
        if start_marker in line and start_idx == -1:
            start_idx = i
            in_block = True
        
        if end_marker in line and in_block:
            end_idx = i
            in_block = False
            # Don't break immediately, in case of duplicates? No, unique enough.
            break
            
    if start_idx != -1 and end_idx != -1:
        print(f"Indenting lines {start_idx+1} to {end_idx+1}")
        for i in range(len(lines)):
            if start_idx <= i <= end_idx:
                # Add 4 spaces
                new_lines.append("    " + lines[i])
            else:
                new_lines.append(lines[i])
                
        # Write back
        with open(FILENAME, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print("Done.")
    else:
        print("Could not find markers.")
        if start_idx == -1: print("Start marker missing.")
        if end_idx == -1: print("End marker missing.")

if __name__ == "__main__":
    fix_file()
