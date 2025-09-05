import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from tkinter import filedialog
import openai
import requests
import difflib
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
RESUMES_DIR = "resumes"
PDF_GENERATOR_ENDPOINT =os.getenv("PDF_GENERATOR_ENDPOINT") 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class ResumeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Resume Analyzer with Change Tracking")
        self.root.geometry("1400x900")
        
        # Store original resume data for comparison
        self.original_resume_data = None
        self.changes_log = []

        # --- Style ---
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0", font=("Arial", 12))
        self.style.configure("TButton", font=("Arial", 12, "bold"))
        self.style.configure("TCombobox", font=("Arial", 12))

        # --- Main Frame ---
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Top Frame for Dropdown ---
        self.top_frame = ttk.Frame(self.main_frame)
        self.top_frame.pack(fill=tk.X, pady=10)

        self.resume_label = ttk.Label(self.top_frame, text="Select Resume:")
        self.resume_label.pack(side=tk.LEFT, padx=(0, 10))

        self.resume_files = self.load_resume_files()
        self.resume_names = [self.get_resume_name(file) for file in self.resume_files]
        
        self.selected_resume = tk.StringVar()
        self.resume_dropdown = ttk.Combobox(self.top_frame, textvariable=self.selected_resume, values=self.resume_names, state="readonly", width=40)
        self.resume_dropdown.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.resume_dropdown.bind("<<ComboboxSelected>>", self.load_resume_content)

        # Reset button to restore original
        self.reset_button = ttk.Button(self.top_frame, text="Reset to Original", command=self.reset_to_original)
        self.reset_button.pack(side=tk.RIGHT, padx=(10, 0))

        # --- Middle Frame for Text Areas ---
        self.middle_frame = ttk.Frame(self.main_frame)
        self.middle_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.middle_frame.columnconfigure(0, weight=2)
        self.middle_frame.columnconfigure(1, weight=1)
        self.middle_frame.columnconfigure(2, weight=1)
        self.middle_frame.rowconfigure(0, weight=1)

        # Left Text Area (Resume JSON) - Made wider
        self.resume_content_frame = ttk.Frame(self.middle_frame, padding=10)
        self.resume_content_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.resume_content_label = ttk.Label(self.resume_content_frame, text="Resume Content (JSON) - Modified sections highlighted")
        self.resume_content_label.pack(anchor="w")
        self.resume_content_text = tk.Text(self.resume_content_frame, wrap=tk.WORD, height=25, width=80, font=("Courier New", 10))
        self.resume_content_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Configure text tags for highlighting
        self.resume_content_text.tag_configure("modified", background="#ffeb3b", foreground="#000")
        self.resume_content_text.tag_configure("added", background="#c8e6c9", foreground="#000")
        self.resume_content_text.tag_configure("removed", background="#ffcdd2", foreground="#000", overstrike=True)

        # Middle Text Area (Job Description)
        self.job_desc_frame = ttk.Frame(self.middle_frame, padding=10)
        self.job_desc_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        self.job_desc_label = ttk.Label(self.job_desc_frame, text="Job Description")
        self.job_desc_label.pack(anchor="w")
        self.job_desc_text = tk.Text(self.job_desc_frame, wrap=tk.WORD, height=25, width=50, font=("Arial", 11))
        self.job_desc_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Right Text Area (Changes Log)
        self.changes_frame = ttk.Frame(self.middle_frame, padding=10)
        self.changes_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self.changes_label = ttk.Label(self.changes_frame, text="Changes Made")
        self.changes_label.pack(anchor="w")
        self.changes_text = tk.Text(self.changes_frame, wrap=tk.WORD, height=25, width=50, font=("Arial", 10))
        self.changes_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.changes_text.config(state=tk.DISABLED)

        # --- Legend Frame ---
        self.legend_frame = ttk.Frame(self.main_frame)
        self.legend_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.legend_frame, text="Legend:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        # Create legend labels with colored backgrounds
        legend_modified = tk.Label(self.legend_frame, text=" Modified ", bg="#ffeb3b", font=("Arial", 9))
        legend_modified.pack(side=tk.LEFT, padx=5)
        
        legend_added = tk.Label(self.legend_frame, text=" Added ", bg="#c8e6c9", font=("Arial", 9))
        legend_added.pack(side=tk.LEFT, padx=5)
        
        legend_removed = tk.Label(self.legend_frame, text=" Removed ", bg="#ffcdd2", font=("Arial", 9))
        legend_removed.pack(side=tk.LEFT, padx=5)

        # --- Bottom Frame for Buttons ---
        self.bottom_frame = ttk.Frame(self.main_frame)
        self.bottom_frame.pack(fill=tk.X, pady=10)

        self.analyze_button = ttk.Button(self.bottom_frame, text="Start Analyzer", command=self.start_analyzer)
        self.analyze_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.view_changes_button = ttk.Button(self.bottom_frame, text="View Detailed Changes", command=self.show_detailed_changes)
        self.view_changes_button.pack(side=tk.LEFT, padx=10, pady=10)
        self.view_changes_button.config(state=tk.DISABLED)

        self.pdf_button = ttk.Button(self.bottom_frame, text="Generate PDF", command=self.trigger_pdf_generation)
        self.pdf_button.pack(side=tk.RIGHT, padx=10, pady=10)

    def load_resume_files(self):
        """Loads all JSON files from the resumes directory."""
        if not os.path.exists(RESUMES_DIR):
            os.makedirs(RESUMES_DIR)
            return []
        return [f for f in os.listdir(RESUMES_DIR) if f.endswith(".json")]

    def get_resume_name(self, filename):
        """Extracts the resume name from the JSON file content."""
        try:
            with open(os.path.join(RESUMES_DIR, filename), 'r') as f:
                data = json.load(f)
                return data.get("name", "Unnamed Resume")
        except (json.JSONDecodeError, FileNotFoundError):
            return "Error Reading Resume"

    def load_resume_content(self, event=None):
        """Loads the content of the selected resume into the text area."""
        selected_name = self.selected_resume.get()
        if not selected_name:
            return
            
        selected_index = self.resume_names.index(selected_name)
        selected_file = self.resume_files[selected_index]
        
        try:
            with open(os.path.join(RESUMES_DIR, selected_file), 'r') as f:
                content = json.load(f)
                self.original_resume_data = content.copy()  # Store original data
                self.resume_content_text.delete("1.0", tk.END)
                self.resume_content_text.insert(tk.END, json.dumps(content, indent=4))
                
                # Clear changes log
                self.changes_text.config(state=tk.NORMAL)
                self.changes_text.delete("1.0", tk.END)
                self.changes_text.config(state=tk.DISABLED)
                self.changes_log = []
                self.view_changes_button.config(state=tk.DISABLED)
                
        except (json.JSONDecodeError, FileNotFoundError) as e:
            messagebox.showerror("Error", f"Failed to load resume: {e}")

    def reset_to_original(self):
        """Resets the resume content to the original version."""
        if self.original_resume_data:
            self.resume_content_text.delete("1.0", tk.END)
            self.resume_content_text.insert(tk.END, json.dumps(self.original_resume_data, indent=4))
            
            # Clear changes log
            self.changes_text.config(state=tk.NORMAL)
            self.changes_text.delete("1.0", tk.END)
            self.changes_text.config(state=tk.DISABLED)
            self.changes_log = []
            self.view_changes_button.config(state=tk.DISABLED)
            
            messagebox.showinfo("Reset", "Resume has been reset to the original version.")
        else:
            messagebox.showwarning("No Original", "No original resume data to reset to. Please select a resume first.")

    def compare_and_highlight_changes(self, original_data, modified_data):
        """Compares original and modified data, highlights changes and logs them."""
        self.changes_log = []
        
        # Compare summary
        if original_data.get("summary") != modified_data.get("summary"):
            self.changes_log.append({
                "section": "Summary",
                "type": "modified",
                "original": original_data.get("summary", ""),
                "modified": modified_data.get("summary", "")
            })

        # Compare experience
        original_exp = original_data.get("experience", [])
        modified_exp = modified_data.get("experience", [])
        
        if len(original_exp) != len(modified_exp):
            self.changes_log.append({
                "section": "Experience",
                "type": "count_changed",
                "original_count": len(original_exp),
                "modified_count": len(modified_exp)
            })
        
        # Compare each experience entry
        for i, (orig, mod) in enumerate(zip(original_exp, modified_exp)):
            if orig != mod:
                self.changes_log.append({
                    "section": f"Experience[{i}]",
                    "type": "modified",
                    "original": orig,
                    "modified": mod
                })

        # Compare skills
        original_skills = set(original_data.get("skills", []))
        modified_skills = set(modified_data.get("skills", []))
        
        added_skills = modified_skills - original_skills
        removed_skills = original_skills - modified_skills
        
        if added_skills:
            self.changes_log.append({
                "section": "Skills",
                "type": "added",
                "items": list(added_skills)
            })
        
        if removed_skills:
            self.changes_log.append({
                "section": "Skills",
                "type": "removed",
                "items": list(removed_skills)
            })

        # Update the changes display
        self.update_changes_display()
        
        # Highlight changes in the JSON text
        self.highlight_json_changes(original_data, modified_data)

    def highlight_json_changes(self, original_data, modified_data):
        """Highlights the changed sections in the JSON text widget."""
        json_text = self.resume_content_text.get("1.0", tk.END)
        self.resume_content_text.delete("1.0", tk.END)
        self.resume_content_text.insert(tk.END, json_text)
        
        # Find and highlight changed sections
        lines = json_text.split('\n')
        
        for i, line in enumerate(lines):
            line_start = f"{i+1}.0"
            line_end = f"{i+1}.end"
            
            # Check if this line contains modified content
            if '"summary"' in line and original_data.get("summary") != modified_data.get("summary"):
                self.resume_content_text.tag_add("modified", line_start, line_end)
            elif '"skills"' in line:
                original_skills = set(original_data.get("skills", []))
                modified_skills = set(modified_data.get("skills", []))
                if original_skills != modified_skills:
                    self.resume_content_text.tag_add("modified", line_start, line_end)
            elif any(keyword in line.lower() for keyword in ['company', 'position', 'description', 'responsibilities']):
                # Check if this is part of a modified experience entry
                if original_data.get("experience") != modified_data.get("experience"):
                    self.resume_content_text.tag_add("modified", line_start, line_end)

    def update_changes_display(self):
        """Updates the changes text widget with a summary of changes."""
        self.changes_text.config(state=tk.NORMAL)
        self.changes_text.delete("1.0", tk.END)
        
        if not self.changes_log:
            self.changes_text.insert(tk.END, "No changes detected.")
            self.changes_text.config(state=tk.DISABLED)
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.changes_text.insert(tk.END, f"Changes made on {timestamp}:\n\n")
        
        for i, change in enumerate(self.changes_log, 1):
            section = change["section"]
            change_type = change["type"]
            
            if change_type == "modified":
                self.changes_text.insert(tk.END, f"{i}. {section}: Content modified\n")
            elif change_type == "added":
                items = ", ".join(change["items"])
                self.changes_text.insert(tk.END, f"{i}. {section}: Added items - {items}\n")
            elif change_type == "removed":
                items = ", ".join(change["items"])
                self.changes_text.insert(tk.END, f"{i}. {section}: Removed items - {items}\n")
            elif change_type == "count_changed":
                self.changes_text.insert(tk.END, f"{i}. {section}: Count changed from {change['original_count']} to {change['modified_count']}\n")
            
            self.changes_text.insert(tk.END, "\n")
        
        self.changes_text.config(state=tk.DISABLED)
        self.view_changes_button.config(state=tk.NORMAL)

    def show_detailed_changes(self):
        """Shows a detailed view of all changes in a new window."""
        if not self.changes_log:
            messagebox.showinfo("No Changes", "No changes to display.")
            return

        # Create new window
        changes_window = tk.Toplevel(self.root)
        changes_window.title("Detailed Changes")
        changes_window.geometry("800x600")
        
        # Create scrollable text widget
        frame = ttk.Frame(changes_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(frame, wrap=tk.WORD, font=("Courier New", 10))
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate with detailed changes
        for i, change in enumerate(self.changes_log, 1):
            text_widget.insert(tk.END, f"=== CHANGE {i}: {change['section']} ===\n")
            
            if change["type"] == "modified":
                text_widget.insert(tk.END, "\nORIGINAL:\n")
                text_widget.insert(tk.END, f"{change['original']}\n\n")
                text_widget.insert(tk.END, "MODIFIED:\n")
                text_widget.insert(tk.END, f"{change['modified']}\n\n")
            elif change["type"] in ["added", "removed"]:
                text_widget.insert(tk.END, f"\n{change['type'].upper()} ITEMS:\n")
                for item in change["items"]:
                    text_widget.insert(tk.END, f"- {item}\n")
                text_widget.insert(tk.END, "\n")
            
            text_widget.insert(tk.END, "-" * 50 + "\n\n")
        
        text_widget.config(state=tk.DISABLED)

    def start_analyzer(self):
        """The main function to start the analysis process."""
        resume_json_str = self.resume_content_text.get("1.0", tk.END)
        job_description = self.job_desc_text.get("1.0", tk.END)

        if not resume_json_str.strip() or not job_description.strip():
            messagebox.showwarning("Input Required", "Please select a resume and provide a job description.")
            return

        if not self.original_resume_data:
            messagebox.showwarning("No Original Data", "Please select a resume first to enable change tracking.")
            return

        try:
            current_resume_data = json.loads(resume_json_str)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON format in the resume content.")
            return

        # Make a copy to avoid modifying the current data
        modified_resume_data = current_resume_data.copy()

        try:
            # 1. Analyze and modify the resume with OpenAI
            messagebox.showinfo("In Progress", "Starting resume analysis with OpenAI...\nThis may take a moment.")
            self.root.update_idletasks() # Update UI to show message

            modified_sections = self.analyze_with_openai(
                modified_resume_data.get("summary", ""),
                modified_resume_data.get("experience", []),
                modified_resume_data.get("skills", []),
                job_description
            )

            if not modified_sections:
                return # Error already shown in analyze_with_openai

            # Update the resume data with the modified sections
            modified_resume_data["summary"] = modified_sections.get("summary", modified_resume_data.get("summary", ""))
            modified_resume_data["experience"] = modified_sections.get("experience", modified_resume_data.get("experience", []))
            modified_resume_data["skills"] = modified_sections.get("skills", modified_resume_data.get("skills", []))

            # Compare and highlight changes
            self.compare_and_highlight_changes(self.original_resume_data, modified_resume_data)

            # Display the modified JSON in the left text box for review
            self.resume_content_text.delete("1.0", tk.END)
            self.resume_content_text.insert(tk.END, json.dumps(modified_resume_data, indent=4))
            
            # Re-apply highlighting after inserting new content
            self.highlight_json_changes(self.original_resume_data, modified_resume_data)
            
            messagebox.showinfo("Analysis Complete", f"Resume has been updated with {len(self.changes_log)} changes detected. Review the highlighted changes before generating the PDF.")

        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def analyze_with_openai(self, summary, experience, skills, job_description):
        """Analyzes and modifies resume sections using OpenAI."""
        if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_OPENAI_API_KEY":
            messagebox.showerror("OpenAI API Key Missing", "Please set your OpenAI API key in the script.")
            return None

        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            prompt = f"""
            You are an expert resume writer. Your task is to tailor a candidate's resume to perfectly match a job description.
            Analyze the provided job description and the candidate's resume sections (summary, experience, and skills).
            Modify the resume sections to align 100% with the job description, add value, and incorporate keywords to make the candidate a top applicant.

            **Job Description:**
            {job_description}

            **Candidate's Current Resume Sections:**
            - **Summary:** {summary}
            - **Experience:** {json.dumps(experience, indent=2)}
            - **Skills:** {json.dumps(skills, indent=2)}

            **Instructions:**
            1.  **Rewrite the Summary:** Make it concise and impactful, directly addressing the key requirements of the job.
            2.  **Enhance Experience:** Do not remove existing experience. Add quantifiable achievements and responsibilities that align with the job description. If the job requires a skill the candidate has but isn't highlighted, emphasize it.
            3.  **Expand Skills:** Add any skills from the job description that are missing from the candidate's skills list. Ensure the final list is comprehensive.

            Return a JSON object with the updated "summary", "experience", and "skills" sections. Do not include any other text or explanations.
            The JSON output should look like this:
            {{
                "summary": "A new, rewritten summary.",
                "experience": [{{ ... updated experience ... }}],
                "skills": [{{ ... updated skills ... }}]
            }}
            """

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            return json.loads(response.choices[0].message.content)

        except openai.APIError as e:
            messagebox.showerror("OpenAI Error", f"OpenAI API error: {e}")
            return None
        except Exception as e:
            messagebox.showerror("Analysis Error", f"Failed to analyze with OpenAI: {e}")
            return None

    def generate_pdf(self, resume_data):
        """Sends the resume data to the PDF generator endpoint."""
        if not PDF_GENERATOR_ENDPOINT or PDF_GENERATOR_ENDPOINT == "YOUR_PDF_GENERATOR_ENDPOINT":
            messagebox.showwarning("PDF Generator", "PDF generator endpoint is not configured.")
            return

        try:
            first_name, last_name = resume_data['name'].split(' ')[0], resume_data['name'].split(' ')[-1]
            save_path = f'{first_name}_{last_name}_Resume.pdf'
            response = requests.post(PDF_GENERATOR_ENDPOINT, json=resume_data)
            response.raise_for_status()  # Raise an exception for bad status codes

            # try:
            #     save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
            # except Exception as e:
            #     messagebox.showerror("File Dialog Error", f"An error occurred with the file dialog: {e}")
            #     return
            
            if not save_path:
                return # User cancelled

            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            messagebox.showinfo("Success", f"PDF successfully generated and saved to {save_path}")

        except requests.exceptions.RequestException as e:
            messagebox.showerror("PDF Generation Error", f"Failed to generate PDF: {e}")

    def trigger_pdf_generation(self):
        """Gets the current resume data from the text box and triggers PDF generation."""
        resume_json_str = self.resume_content_text.get("1.0", tk.END)
        if not resume_json_str.strip():
            messagebox.showwarning("Empty Resume", "The resume content is empty. Please analyze a resume first.")
            return
        try:
            resume_data = json.loads(resume_json_str)
            self.generate_pdf(resume_data)
        except json.JSONDecodeError:
            messagebox.showerror("Invalid JSON", "The content of the resume is not valid JSON.")


if __name__ == "__main__":
    root = tk.Tk()
    app = ResumeApp(root)
    root.mainloop()