"""
Menu Catalog Management Viewport for Administrators and Managers.
Allows adding/editing dishes, price validation, category assignment,
and status toggling.
"""
import tkinter as tk
from tkinter import ttk, messagebox


class MenuView(ttk.Frame):
    """Catalog manager supporting item CRUD and category maintenance."""
    def __init__(self, parent, menu_service, get_session_callback, on_menu_changed_callback=None):
        super().__init__(parent)
        self.menu_service = menu_service
        self.get_session = get_session_callback
        self.on_menu_changed = on_menu_changed_callback

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Top toolbar
        toolbar = ttk.Frame(self, padding="8")
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text="Category Filter:").pack(side=tk.LEFT, padx=(0, 4))
        self.filter_var = tk.StringVar(value="All")
        self.filter_combo = ttk.Combobox(toolbar, textvariable=self.filter_var, state="readonly", width=16)
        self.filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self._render_table())

        ttk.Button(toolbar, text="Add New Item", command=self._open_add_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Edit Selected", command=self._open_edit_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Toggle Active Status", command=self._toggle_status).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Manage Categories", command=self._open_categories_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side=tk.RIGHT, padx=4)

        # Items Table
        table_frame = ttk.Frame(self, padding="8 0 8 8")
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "name", "category", "price", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Dish / Item Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("price", text="Price (INR)")
        self.tree.heading("status", text="Availability Status")

        self.tree.column("id", width=50, anchor=tk.CENTER)
        self.tree.column("name", width=260, anchor=tk.W)
        self.tree.column("category", width=140, anchor=tk.W)
        self.tree.column("price", width=100, anchor=tk.E)
        self.tree.column("status", width=120, anchor=tk.CENTER)

        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh(self):
        """Fetches all items from database including inactive."""
        try:
            self.items = self.menu_service.get_all_menu_items(active_only=False)
            categories = ["All"] + self.menu_service.get_categories()
            self.filter_combo["values"] = categories
            if self.filter_var.get() not in categories:
                self.filter_var.set("All")
            self._render_table()
        except Exception as ex:
            messagebox.showerror("Error", str(ex), parent=self)

    def _render_table(self):
        cat = self.filter_var.get()
        for row in self.tree.get_children():
            self.tree.delete(row)

        for item in self.items:
            if cat != "All" and item.get("category") != cat:
                continue

            status = "Active" if item.get("is_active") else "Inactive"
            price = float(item.get("price", 0.0))
            name = item.get("item_name") or item.get("name", "")
            self.tree.insert(
                "",
                tk.END,
                values=(item["item_id"], name, item["category"], f"₹{price:.2f}", status)
            )

    def _open_add_dialog(self):
        ItemFormDialog(self, self.menu_service, self.get_session(), on_save=self._on_saved)

    def _open_edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an item to edit.", parent=self)
            return
        item_id = int(self.tree.item(sel[0], "values")[0])
        item = self.menu_service.get_item_by_id(item_id)
        if item:
            ItemFormDialog(self, self.menu_service, self.get_session(), item_data=item, on_save=self._on_saved)

    def _toggle_status(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an item to toggle status.", parent=self)
            return
        item_id = int(self.tree.item(sel[0], "values")[0])
        curr_status = self.tree.item(sel[0], "values")[4]
        new_active = False if curr_status == "Active" else True
        try:
            ok, msg = self.menu_service.toggle_item_status(admin_session=self.get_session(), item_id=item_id, is_active=new_active)
            if ok:
                self.refresh()
                if self.on_menu_changed:
                    self.on_menu_changed()
                status_str = "Active" if new_active else "Inactive"
                messagebox.showinfo("Status Updated", f"Item #{item_id} is now {status_str}.", parent=self)
            else:
                messagebox.showerror("Error", msg, parent=self)
        except Exception as ex:
            messagebox.showerror("Error", str(ex), parent=self)

    def _open_categories_dialog(self):
        CategoriesDialog(self, self.menu_service, self.get_session(), on_update=self.refresh)

    def _on_saved(self):
        self.refresh()
        if self.on_menu_changed:
            self.on_menu_changed()


class ItemFormDialog(tk.Toplevel):
    """Modal for creating or editing menu items."""
    def __init__(self, parent, menu_service, session, item_data=None, on_save=None):
        super().__init__(parent)
        self.menu_service = menu_service
        self.session = session
        self.item_data = item_data
        self.on_save = on_save

        is_edit = item_data is not None
        self.title("Edit Menu Item" if is_edit else "Add New Menu Item")
        self.geometry("380x320")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(frame, text="Item Name:").pack(anchor=tk.W, pady=(0, 2))
        initial_name = (item_data.get("item_name") or item_data.get("name", "")) if item_data else ""
        self.name_var = tk.StringVar(value=initial_name)
        ttk.Entry(frame, textvariable=self.name_var).pack(fill=tk.X, pady=(0, 10))

        # Category
        ttk.Label(frame, text="Category:").pack(anchor=tk.W, pady=(0, 2))
        categories = self.menu_service.get_categories()
        default_cat = item_data.get("category", categories[0] if categories else "") if item_data else (categories[0] if categories else "")
        self.cat_var = tk.StringVar(value=default_cat)
        self.cat_combo = ttk.Combobox(frame, textvariable=self.cat_var, values=categories, state="readonly")
        self.cat_combo.pack(fill=tk.X, pady=(0, 10))

        # Price
        ttk.Label(frame, text="Price (INR):").pack(anchor=tk.W, pady=(0, 2))
        self.price_var = tk.StringVar(value=str(item_data.get("price", "")) if item_data else "")
        ttk.Entry(frame, textvariable=self.price_var).pack(fill=tk.X, pady=(0, 16))

        # Save Button
        btn = ttk.Button(frame, text="Save Item", command=self._save)
        btn.pack(fill=tk.X, ipady=4)

    def _save(self):
        name = self.name_var.get().strip()
        cat = self.cat_var.get().strip()
        price_str = self.price_var.get().strip()

        if not name:
            messagebox.showwarning("Validation", "Item name is required.", parent=self)
            return
        try:
            price = float(price_str)
            if price <= 0:
                raise ValueError("Price must be greater than zero.")
        except ValueError:
            messagebox.showwarning("Validation", "Please enter a valid numeric price greater than zero.", parent=self)
            return

        try:
            if self.item_data:
                ok, msg = self.menu_service.update_menu_item(
                    admin_session=self.session,
                    item_id=self.item_data["item_id"],
                    item_name=name,
                    category=cat,
                    price_input=price
                )
            else:
                ok, new_id, msg = self.menu_service.add_menu_item(
                    admin_session=self.session,
                    item_name=name,
                    category=cat,
                    price_input=price
                )
            if ok:
                self.destroy()
                if self.on_save:
                    self.on_save()
            else:
                messagebox.showerror("Error", msg, parent=self)
        except Exception as ex:
            messagebox.showerror("Error", str(ex), parent=self)


class CategoriesDialog(tk.Toplevel):
    """Dialog for viewing and adding custom categories."""
    def __init__(self, parent, menu_service, session, on_update=None):
        super().__init__(parent)
        self.menu_service = menu_service
        self.session = session
        self.on_update = on_update

        self.title("Manage Menu Categories")
        self.geometry("360x380")
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding="14")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Existing Categories:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.cat_list = tk.Listbox(frame, height=8)
        self.cat_list.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Add category
        add_frame = ttk.Frame(frame)
        add_frame.pack(fill=tk.X, pady=(0, 6))

        self.new_cat_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.new_cat_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(add_frame, text="Add Category", command=self._add_cat).pack(side=tk.RIGHT)

        ttk.Button(frame, text="Close", command=self.destroy).pack(fill=tk.X, pady=(6, 0))

        self._refresh()

    def _refresh(self):
        self.cat_list.delete(0, tk.END)
        for cat in self.menu_service.get_categories():
            self.cat_list.insert(tk.END, cat)

    def _add_cat(self):
        cat_name = self.new_cat_var.get().strip()
        if not cat_name:
            return
        try:
            ok, msg = self.menu_service.add_category(admin_session=self.session, category_name=cat_name)
            if ok:
                self.new_cat_var.set("")
                self._refresh()
                if self.on_update:
                    self.on_update()
            else:
                messagebox.showerror("Error", msg, parent=self)
        except Exception as ex:
            messagebox.showerror("Error", str(ex), parent=self)
