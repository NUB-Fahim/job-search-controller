"""
ui.py
-----
All Tkinter/ttk screens (views) for the Job Portal Management System.
Screens are plain ttk.Frame subclasses. They talk to the app only through
the `controller` object (see app.py) and to data only through `backend`.
No sqlite3 or business-logic code should live here.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import backend

PAD = 10


# ==================================================================
# Shared helpers
# ==================================================================
class ScrollableFrame(ttk.Frame):
    """A frame with a vertical scrollbar, for long lists."""

    def __init__(self, parent, *a, **kw):
        super().__init__(parent, *a, **kw)
        canvas = tk.Canvas(self, highlightthickness=0)
        vscroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = ttk.Frame(canvas)

        self.body.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)


def labeled_entry(parent, label, row, show=None, width=32):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
    var = tk.StringVar()
    entry = ttk.Entry(parent, textvariable=var, show=show, width=width)
    entry.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 0))
    return var, entry


# ==================================================================
# Auth screens
# ==================================================================
class LoginFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=30)
        self.controller = controller

        card = ttk.Frame(self, padding=30, style="Card.TFrame")
        card.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(card, text="Job Portal", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, pady=(0, 20)
        )

        self.email_var, _ = labeled_entry(card, "Email", 1)
        self.pw_var, pw_entry = labeled_entry(card, "Password", 2, show="*")

        btn_row = ttk.Frame(card)
        btn_row.grid(row=3, column=0, columnspan=2, pady=(20, 5), sticky="ew")
        ttk.Button(btn_row, text="Login", style="Accent.TButton", command=self.do_login).pack(
            side="left", expand=True, fill="x", padx=(0, 5)
        )
        ttk.Button(btn_row, text="Create Account", command=self.go_register).pack(
            side="left", expand=True, fill="x", padx=(5, 0)
        )

        ttk.Label(
            card, text="Default admin: admin@jobportal.local / Admin@123",
            style="Hint.TLabel"
        ).grid(row=4, column=0, columnspan=2, pady=(15, 0))

        self.bind("<Return>", lambda e: self.do_login())
        pw_entry.bind("<Return>", lambda e: self.do_login())

    def go_register(self):
        self.controller.show_frame("RegisterFrame")

    def do_login(self):
        try:
            user = backend.login_user(self.email_var.get(), self.pw_var.get())
        except ValueError as e:
            messagebox.showerror("Login failed", str(e))
            return
        self.controller.current_user = user
        self.email_var.set("")
        self.pw_var.set("")
        self.controller.route_after_login()


class RegisterFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=30)
        self.controller = controller

        card = ttk.Frame(self, padding=30, style="Card.TFrame")
        card.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(card, text="Create Account", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, pady=(0, 20)
        )

        self.email_var, _ = labeled_entry(card, "Email", 1)
        self.pw_var, _ = labeled_entry(card, "Password", 2, show="*")
        self.pw2_var, _ = labeled_entry(card, "Confirm Password", 3, show="*")

        ttk.Label(card, text="Role").grid(row=4, column=0, sticky="w", pady=4)
        self.role_var = tk.StringVar(value="seeker")
        role_box = ttk.Combobox(
            card, textvariable=self.role_var, values=["seeker", "employer"],
            state="readonly", width=29
        )
        role_box.grid(row=4, column=1, sticky="ew", pady=4, padx=(8, 0))

        btn_row = ttk.Frame(card)
        btn_row.grid(row=5, column=0, columnspan=2, pady=(20, 5), sticky="ew")
        ttk.Button(btn_row, text="Register", style="Accent.TButton", command=self.do_register).pack(
            side="left", expand=True, fill="x", padx=(0, 5)
        )
        ttk.Button(btn_row, text="Back to Login", command=self.go_login).pack(
            side="left", expand=True, fill="x", padx=(5, 0)
        )

    def go_login(self):
        self.controller.show_frame("LoginFrame")

    def do_register(self):
        if self.pw_var.get() != self.pw2_var.get():
            messagebox.showerror("Registration failed", "Passwords do not match.")
            return
        try:
            backend.register_user(self.email_var.get(), self.pw_var.get(), self.role_var.get())
        except ValueError as e:
            messagebox.showerror("Registration failed", str(e))
            return
        messagebox.showinfo("Success", "Account created. You can now log in.")
        self.controller.show_frame("LoginFrame")


# ==================================================================
# Shared top bar for logged-in screens
# ==================================================================
class TopBar(ttk.Frame):
    def __init__(self, parent, controller, title):
        super().__init__(parent, padding=(15, 10), style="Header.TFrame")
        self.controller = controller
        ttk.Label(self, text=title, style="HeaderTitle.TLabel").pack(side="left")

        right = ttk.Frame(self, style="Header.TFrame")
        right.pack(side="right")

        user = controller.current_user
        who = f"{user['email']} ({user['role']})" if user else ""
        ttk.Label(right, text=who, style="HeaderSub.TLabel").pack(side="left", padx=(0, 15))
        ttk.Button(right, text="🔔 Notifications", command=controller.open_notifications).pack(
            side="left", padx=5
        )
        ttk.Button(right, text="Logout", command=controller.logout).pack(side="left", padx=5)


# ==================================================================
# Seeker dashboard
# ==================================================================
class SeekerDashboard(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        TopBar(self, controller, "Job Seeker Dashboard").pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        self.search_tab = JobSearchTab(nb, controller)
        self.applied_tab = AppliedJobsTab(nb, controller)
        self.profile_tab = SeekerProfileTab(nb, controller)
        self.feedback_tab = FeedbackTab(nb, controller)

        nb.add(self.search_tab, text="Search Jobs")
        nb.add(self.applied_tab, text="My Applications")
        nb.add(self.profile_tab, text="My Profile")
        nb.add(self.feedback_tab, text="Feedback")

        self.notebook = nb
        nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event):
        tab = self.notebook.select()
        widget = self.nametowidget(tab)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def refresh(self):
        self.search_tab.refresh()
        self.applied_tab.refresh()
        self.profile_tab.refresh()


class JobSearchTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller

        filt = ttk.Frame(self)
        filt.pack(fill="x", pady=(0, 10))

        self.kw_var = tk.StringVar()
        self.loc_var = tk.StringVar()
        self.type_var = tk.StringVar()
        self.sal_var = tk.StringVar()

        ttk.Label(filt, text="Keyword").grid(row=0, column=0, sticky="w")
        ttk.Entry(filt, textvariable=self.kw_var, width=20).grid(row=1, column=0, padx=(0, 8))

        ttk.Label(filt, text="Location").grid(row=0, column=1, sticky="w")
        ttk.Entry(filt, textvariable=self.loc_var, width=16).grid(row=1, column=1, padx=(0, 8))

        ttk.Label(filt, text="Type").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            filt, textvariable=self.type_var, values=[""] + backend.JOB_TYPES,
            state="readonly", width=13
        ).grid(row=1, column=2, padx=(0, 8))

        ttk.Label(filt, text="Min Salary").grid(row=0, column=3, sticky="w")
        ttk.Entry(filt, textvariable=self.sal_var, width=10).grid(row=1, column=3, padx=(0, 8))

        ttk.Button(filt, text="Search", style="Accent.TButton", command=self.refresh).grid(
            row=1, column=4, padx=(8, 0)
        )

        cols = ("title", "company_location", "type", "salary")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (260, 220, 100, 140)):
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.open_job)

        self._rows = []

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="View & Apply", command=self.open_job).pack(side="left")

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            min_sal = int(self.sal_var.get()) if self.sal_var.get().strip() else None
        except ValueError:
            min_sal = None
        jobs = backend.search_jobs(
            keyword=self.kw_var.get(), location=self.loc_var.get(),
            jtype=self.type_var.get(), min_salary=min_sal, status="approved"
        )
        self._rows = jobs
        for j in jobs:
            sal = ""
            if j["salary_min"] or j["salary_max"]:
                sal = f"{j['salary_min'] or '?'} - {j['salary_max'] or '?'}"
            self.tree.insert(
                "", "end", iid=str(j["id"]),
                values=(j["title"], j["location"] or "—", j["type"] or "—", sal),
            )

    def open_job(self, event=None):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a job", "Please select a job first.")
            return
        job_id = int(sel[0])
        JobDetailDialog(self, self.controller, job_id, allow_apply=True)


class JobDetailDialog(tk.Toplevel):
    def __init__(self, parent, controller, job_id, allow_apply=False):
        super().__init__(parent)
        self.controller = controller
        self.job = backend.get_job(job_id)
        self.title(self.job["title"])
        self.geometry("520x480")

        frm = ttk.Frame(self, padding=15)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text=self.job["title"], font=("Segoe UI", 14, "bold")).pack(anchor="w")
        meta = f"{self.job['location'] or '—'} · {self.job['type'] or '—'} · {self.job['experience'] or '—'}"
        ttk.Label(frm, text=meta, foreground="#555").pack(anchor="w", pady=(2, 10))

        txt = tk.Text(frm, wrap="word", height=15)
        txt.insert("1.0", self.job["description"])
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)

        if allow_apply:
            ttk.Label(frm, text="Cover note (optional)").pack(anchor="w", pady=(10, 2))
            self.note = tk.Text(frm, height=3)
            self.note.pack(fill="x")
            ttk.Button(frm, text="Apply Now", style="Accent.TButton", command=self.apply).pack(
                anchor="e", pady=(10, 0)
            )

    def apply(self):
        try:
            backend.apply_to_job(
                self.controller.current_user["id"], self.job["id"],
                self.note.get("1.0", "end").strip()
            )
        except ValueError as e:
            messagebox.showerror("Could not apply", str(e))
            return
        messagebox.showinfo("Applied", "Your application has been submitted!")
        self.destroy()


class AppliedJobsTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller
        cols = ("title", "location", "type", "status", "applied_on")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (240, 160, 100, 130, 150)):
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        apps = backend.list_applications_for_seeker(self.controller.current_user["id"])
        for a in apps:
            self.tree.insert(
                "", "end",
                values=(a["title"], a["location"] or "—", a["type"] or "—",
                        a["status"], a["created_at"][:10]),
            )


class SeekerProfileTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller

        form = ttk.Frame(self)
        form.pack(anchor="w", fill="x")

        self.name_var, _ = labeled_entry(form, "Full Name", 0, width=40)
        self.phone_var, _ = labeled_entry(form, "Phone", 1, width=40)
        ttk.Label(form, text="Skills (comma-separated)").grid(row=2, column=0, sticky="w", pady=4)
        self.skills_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.skills_var, width=40).grid(
            row=2, column=1, sticky="ew", pady=4, padx=(8, 0)
        )

        ttk.Button(form, text="Save Profile", style="Accent.TButton", command=self.save).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(15, 5)
        )

        ttk.Separator(self).pack(fill="x", pady=15)

        resume_row = ttk.Frame(self)
        resume_row.pack(fill="x")
        self.resume_label = ttk.Label(resume_row, text="No resume uploaded.")
        self.resume_label.pack(side="left")
        ttk.Button(resume_row, text="Upload Resume", command=self.upload).pack(side="right")

    def refresh(self):
        profile = backend.get_seeker_profile(self.controller.current_user["id"])
        if profile:
            self.name_var.set(profile.get("name") or "")
            self.phone_var.set(profile.get("phone") or "")
            self.skills_var.set(profile.get("skills") or "")
            if profile.get("resume_path"):
                self.resume_label.configure(text=f"Resume: {profile['resume_path']}")
            else:
                self.resume_label.configure(text="No resume uploaded.")

    def save(self):
        try:
            backend.update_seeker_profile(
                self.controller.current_user["id"], self.name_var.get(),
                self.phone_var.get(), self.skills_var.get()
            )
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return
        messagebox.showinfo("Saved", "Profile updated.")

    def upload(self):
        path = filedialog.askopenfilename(
            title="Select resume",
            filetypes=[("Documents", "*.pdf *.doc *.docx *.txt *.rtf")],
        )
        if not path:
            return
        try:
            backend.upload_resume(self.controller.current_user["id"], path)
        except ValueError as e:
            messagebox.showerror("Upload failed", str(e))
            return
        messagebox.showinfo("Success", "Resume uploaded.")
        self.refresh()


# ==================================================================
# Employer dashboard
# ==================================================================
class EmployerDashboard(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        TopBar(self, controller, "Employer Dashboard").pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        self.post_tab = PostJobTab(nb, controller)
        self.myjobs_tab = MyJobsTab(nb, controller)
        self.profile_tab = EmployerProfileTab(nb, controller)
        self.feedback_tab = FeedbackTab(nb, controller)

        nb.add(self.post_tab, text="Post a Job")
        nb.add(self.myjobs_tab, text="My Jobs & Applicants")
        nb.add(self.profile_tab, text="Company Profile")
        nb.add(self.feedback_tab, text="Feedback")

        self.notebook = nb
        nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event):
        widget = self.nametowidget(self.notebook.select())
        if hasattr(widget, "refresh"):
            widget.refresh()

    def refresh(self):
        self.myjobs_tab.refresh()
        self.profile_tab.refresh()


class PostJobTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller

        form = ttk.Frame(self)
        form.pack(fill="x")

        self.title_var, _ = labeled_entry(form, "Job Title", 0, width=45)
        self.loc_var, _ = labeled_entry(form, "Location", 1, width=45)

        ttk.Label(form, text="Type").grid(row=2, column=0, sticky="w", pady=4)
        self.type_var = tk.StringVar(value=backend.JOB_TYPES[0])
        ttk.Combobox(
            form, textvariable=self.type_var, values=backend.JOB_TYPES,
            state="readonly", width=42
        ).grid(row=2, column=1, sticky="ew", pady=4, padx=(8, 0))

        self.exp_var, _ = labeled_entry(form, "Experience Required", 3, width=45)
        self.smin_var, _ = labeled_entry(form, "Salary Min", 4, width=45)
        self.smax_var, _ = labeled_entry(form, "Salary Max", 5, width=45)

        ttk.Label(form, text="Description").grid(row=6, column=0, sticky="nw", pady=4)
        self.desc_text = tk.Text(form, width=45, height=8)
        self.desc_text.grid(row=6, column=1, sticky="ew", pady=4, padx=(8, 0))

        ttk.Button(
            form, text="Submit for Approval", style="Accent.TButton", command=self.submit
        ).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(15, 0))

    def submit(self):
        try:
            backend.create_job(
                self.controller.current_user["id"], self.title_var.get(),
                self.desc_text.get("1.0", "end"), self.loc_var.get(), self.type_var.get(),
                self.exp_var.get(), self.smin_var.get(), self.smax_var.get(),
                submit_for_approval=True,
            )
        except ValueError as e:
            messagebox.showerror("Could not post job", str(e))
            return
        messagebox.showinfo("Submitted", "Job submitted for admin approval.")
        for var in (self.title_var, self.loc_var, self.exp_var, self.smin_var, self.smax_var):
            var.set("")
        self.desc_text.delete("1.0", "end")
        self.controller.frames["EmployerDashboard"].refresh()


class MyJobsTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller
        cols = ("title", "location", "type", "status", "posted")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (220, 150, 100, 100, 140)):
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.view_applicants)

        ttk.Button(self, text="View Applicants", command=self.view_applicants).pack(
            anchor="w", pady=(8, 0)
        )

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        jobs = backend.list_jobs_by_employer(self.controller.current_user["id"])
        for j in jobs:
            self.tree.insert(
                "", "end", iid=str(j["id"]),
                values=(j["title"], j["location"] or "—", j["type"] or "—",
                        j["status"], j["created_at"][:10]),
            )

    def view_applicants(self, event=None):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a job", "Please select a job first.")
            return
        ApplicantsDialog(self, self.controller, int(sel[0]))


class ApplicantsDialog(tk.Toplevel):
    def __init__(self, parent, controller, job_id):
        super().__init__(parent)
        self.controller = controller
        self.job_id = job_id
        job = backend.get_job(job_id)
        self.title(f"Applicants — {job['title']}")
        self.geometry("640x420")

        cols = ("name", "email", "skills", "status", "applied_on")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (140, 180, 160, 110, 110)):
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        btns = ttk.Frame(self, padding=(10, 0, 10, 10))
        btns.pack(fill="x")
        ttk.Label(btns, text="Update status:").pack(side="left")
        self.status_var = tk.StringVar(value=backend.APPLICATION_STATUSES[0])
        ttk.Combobox(
            btns, textvariable=self.status_var, values=backend.APPLICATION_STATUSES,
            state="readonly", width=15
        ).pack(side="left", padx=8)
        ttk.Button(btns, text="Apply Update", command=self.update_status).pack(side="left")

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        apps = backend.list_applications_for_job(self.job_id)
        for a in apps:
            self.tree.insert(
                "", "end", iid=str(a["id"]),
                values=(a["name"] or "—", a["email"], a["skills"] or "—",
                        a["status"], a["created_at"][:10]),
            )

    def update_status(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select an applicant", "Please select an applicant first.")
            return
        try:
            backend.update_application_status(
                int(sel[0]), self.status_var.get(), self.controller.current_user["id"]
            )
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return
        self.refresh()


class EmployerProfileTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller
        form = ttk.Frame(self)
        form.pack(anchor="w", fill="x")

        self.company_var, _ = labeled_entry(form, "Company Name", 0, width=40)
        self.website_var, _ = labeled_entry(form, "Website", 1, width=40)
        self.industry_var, _ = labeled_entry(form, "Industry", 2, width=40)

        self.approved_label = ttk.Label(form, text="")
        self.approved_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Button(form, text="Save", style="Accent.TButton", command=self.save).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(15, 0)
        )

    def refresh(self):
        profile = backend.get_employer_profile(self.controller.current_user["id"])
        if profile:
            self.company_var.set(profile.get("company") or "")
            self.website_var.set(profile.get("website") or "")
            self.industry_var.set(profile.get("industry") or "")
            status = "✅ Approved by admin" if profile.get("approved") else "⏳ Pending admin approval"
            self.approved_label.configure(text=status)

    def save(self):
        try:
            backend.update_employer_profile(
                self.controller.current_user["id"], self.company_var.get(),
                self.website_var.get(), self.industry_var.get()
            )
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return
        messagebox.showinfo("Saved", "Company profile updated.")


# ==================================================================
# Shared: Feedback tab (seeker + employer)
# ==================================================================
class FeedbackTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller

        ttk.Label(self, text="Subject").pack(anchor="w")
        self.subject_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.subject_var, width=50).pack(anchor="w", pady=(0, 8))

        ttk.Label(self, text="Message").pack(anchor="w")
        self.msg_text = tk.Text(self, width=50, height=8)
        self.msg_text.pack(anchor="w")

        ttk.Button(self, text="Submit Feedback", style="Accent.TButton", command=self.submit).pack(
            anchor="w", pady=(10, 0)
        )

    def submit(self):
        try:
            backend.submit_feedback(
                self.controller.current_user["id"], self.subject_var.get(),
                self.msg_text.get("1.0", "end")
            )
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return
        messagebox.showinfo("Thank you", "Your feedback has been submitted.")
        self.subject_var.set("")
        self.msg_text.delete("1.0", "end")

    def refresh(self):
        pass


# ==================================================================
# Admin dashboard
# ==================================================================
class AdminDashboard(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        TopBar(self, controller, "Admin Dashboard").pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        self.overview_tab = AdminOverviewTab(nb, controller)
        self.users_tab = AdminUsersTab(nb, controller)
        self.jobs_tab = AdminJobsTab(nb, controller)
        self.feedback_tab = AdminFeedbackTab(nb, controller)

        nb.add(self.overview_tab, text="Overview")
        nb.add(self.users_tab, text="Manage Users")
        nb.add(self.jobs_tab, text="Manage Jobs")
        nb.add(self.feedback_tab, text="Feedback")

        self.notebook = nb
        nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event):
        widget = self.nametowidget(self.notebook.select())
        if hasattr(widget, "refresh"):
            widget.refresh()

    def refresh(self):
        self.overview_tab.refresh()
        self.users_tab.refresh()
        self.jobs_tab.refresh()
        self.feedback_tab.refresh()


class AdminOverviewTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller
        self.cards_frame = ttk.Frame(self)
        self.cards_frame.pack(fill="x")

    def refresh(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        stats = backend.admin_stats()
        labels = [
            ("Total Users", stats["total_users"]),
            ("Job Seekers", stats["total_seekers"]),
            ("Employers", stats["total_employers"]),
            ("Total Jobs", stats["total_jobs"]),
            ("Pending Jobs", stats["pending_jobs"]),
            ("Applications", stats["total_applications"]),
            ("Open Feedback", stats["open_feedback"]),
        ]
        for i, (name, val) in enumerate(labels):
            card = ttk.Frame(self.cards_frame, padding=15, style="Card.TFrame")
            card.grid(row=i // 4, column=i % 4, padx=8, pady=8, sticky="ew")
            ttk.Label(card, text=str(val), font=("Segoe UI", 20, "bold")).pack()
            ttk.Label(card, text=name, style="Hint.TLabel").pack()


class AdminUsersTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller

        filt = ttk.Frame(self)
        filt.pack(fill="x", pady=(0, 8))
        ttk.Label(filt, text="Filter role:").pack(side="left")
        self.role_var = tk.StringVar(value="")
        ttk.Combobox(
            filt, textvariable=self.role_var, values=["", "seeker", "employer", "admin"],
            state="readonly", width=12
        ).pack(side="left", padx=8)
        ttk.Button(filt, text="Refresh", command=self.refresh).pack(side="left")

        cols = ("email", "role", "verified", "active", "created")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (220, 100, 90, 90, 150)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Approve Employer", command=self.approve).pack(side="left")
        ttk.Button(actions, text="Deactivate", command=lambda: self.set_active(False)).pack(
            side="left", padx=8
        )
        ttk.Button(actions, text="Activate", command=lambda: self.set_active(True)).pack(
            side="left"
        )

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        users = backend.list_users(self.role_var.get() or None)
        for u in users:
            self.tree.insert(
                "", "end", iid=str(u["id"]),
                values=(u["email"], u["role"], "Yes" if u["is_verified"] else "No",
                        "Yes" if u["is_active"] else "No", u["created_at"][:10]),
            )

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a user", "Please select a user first.")
            return None
        return int(sel[0])

    def approve(self):
        uid = self._selected_id()
        if uid is None:
            return
        backend.approve_employer(uid, self.controller.current_user["id"])
        messagebox.showinfo("Done", "Employer approved (if applicable).")
        self.refresh()

    def set_active(self, active):
        uid = self._selected_id()
        if uid is None:
            return
        backend.set_user_active(uid, active, self.controller.current_user["id"])
        self.refresh()


class AdminJobsTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller

        ttk.Label(self, text="Jobs pending approval", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        cols = ("title", "company", "location", "type", "posted")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (220, 160, 140, 100, 140)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, pady=(6, 8))

        actions = ttk.Frame(self)
        actions.pack(fill="x")
        ttk.Button(actions, text="Approve", style="Accent.TButton", command=self.approve).pack(
            side="left"
        )
        ttk.Button(actions, text="Reject", command=self.reject).pack(side="left", padx=8)
        ttk.Button(actions, text="View Details", command=self.view).pack(side="left")

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        jobs = backend.list_pending_jobs()
        for j in jobs:
            self.tree.insert(
                "", "end", iid=str(j["id"]),
                values=(j["title"], j.get("company") or "—", j["location"] or "—",
                        j["type"] or "—", j["created_at"][:10]),
            )

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a job", "Please select a job first.")
            return None
        return int(sel[0])

    def approve(self):
        jid = self._selected_id()
        if jid is None:
            return
        backend.update_job_status(jid, "approved", self.controller.current_user["id"])
        self.refresh()

    def reject(self):
        jid = self._selected_id()
        if jid is None:
            return
        backend.update_job_status(jid, "rejected", self.controller.current_user["id"])
        self.refresh()

    def view(self):
        jid = self._selected_id()
        if jid is None:
            return
        JobDetailDialog(self, self.controller, jid, allow_apply=False)


class AdminFeedbackTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=PAD)
        self.controller = controller
        cols = ("email", "subject", "status", "created")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (200, 240, 100, 140)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.view_message)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Mark Reviewed", command=lambda: self.set_status("reviewed")).pack(
            side="left"
        )
        ttk.Button(actions, text="Close", command=lambda: self.set_status("closed")).pack(
            side="left", padx=8
        )

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for f in backend.list_feedback():
            self.tree.insert(
                "", "end", iid=str(f["id"]),
                values=(f.get("email") or "—", f["subject"], f["status"], f["created_at"][:10]),
            )

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select feedback", "Please select a feedback item first.")
            return None
        return int(sel[0])

    def set_status(self, status):
        fid = self._selected()
        if fid is None:
            return
        backend.update_feedback_status(fid, status)
        self.refresh()

    def view_message(self, event=None):
        fid = self._selected()
        if fid is None:
            return
        items = {f["id"]: f for f in backend.list_feedback()}
        f = items.get(fid)
        if f:
            messagebox.showinfo(f["subject"], f["message"])


# ==================================================================
# Notifications window
# ==================================================================
class NotificationsWindow(tk.Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.title("Notifications")
        self.geometry("420x420")

        cols = ("type", "message", "when")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=16)
        self.tree.heading("type", text="Type")
        self.tree.heading("message", text="Message")
        self.tree.heading("when", text="When")
        self.tree.column("type", width=100)
        self.tree.column("message", width=220)
        self.tree.column("when", width=90)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Button(self, text="Mark all read", command=self.mark_all).pack(pady=(0, 10))
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        notes = backend.list_notifications(self.controller.current_user["id"])
        for n in notes:
            prefix = "🔵 " if not n["is_read"] else ""
            self.tree.insert(
                "", "end",
                values=(prefix + n["type"], n["payload"], n["created_at"][:16]),
            )

    def mark_all(self):
        backend.mark_all_notifications_read(self.controller.current_user["id"])
        self.refresh()
