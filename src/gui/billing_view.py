"""
POS Order Billing Viewport for Cashiers and Managers.
Features live menu item search, quantity management, live GST breakdown,
and automated receipt/PDF invoice generation.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from src.billing.cart import OrderCart


class ReceiptDialog(tk.Toplevel):
    """Modal displaying formatted thermal receipt with export actions."""
    def __init__(self, parent, receipt_text, bill_data, export_service):
        super().__init__(parent)
        self.receipt_text = receipt_text
        self.bill_data = bill_data
        self.export_service = export_service

        bill_num = bill_data.get("bill_number") or bill_data.get("bill_id")
        self.title(f"Receipt - Bill #{bill_num}")
        self.geometry("450x600")
        self.transient(parent)
        self.grab_set()

        # Text display
        frame = ttk.Frame(self, padding="12")
        frame.pack(fill=tk.BOTH, expand=True)

        txt = tk.Text(frame, font=("Courier New", 10), wrap=tk.NONE)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        txt.insert("1.0", receipt_text)
        txt.configure(state=tk.DISABLED)

        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        btn_frame = ttk.Frame(self, padding="10")
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Save PDF Invoice", command=self._save_pdf).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def _save_pdf(self):
        bill_num = self.bill_data.get("bill_number") or self.bill_data.get("bill_id")
        default_name = f"invoice_{bill_num}.pdf"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")],
            initialfile=default_name,
            title="Save Invoice PDF"
        )
        if file_path:
            try:
                ok, msg = self.export_service.export_invoice_to_pdf(self.bill_data.get("bill_id"), file_path)
                if ok:
                    messagebox.showinfo("Export Successful", f"Invoice saved to:\n{file_path}", parent=self)
                else:
                    messagebox.showerror("Export Failed", msg, parent=self)
            except Exception as ex:
                messagebox.showerror("Export Failed", str(ex), parent=self)


class BillingView(ttk.Frame):
    """POS billing screen containing menu catalog and live order cart."""
    def __init__(self, parent, menu_service, billing_service, export_service, get_session_callback):
        super().__init__(parent)
        self.menu_service = menu_service
        self.billing_service = billing_service
        self.export_service = export_service
        self.get_session = get_session_callback

        self.cart = OrderCart()
        self.menu_items = []

        self._build_ui()
        self.refresh_menu()

    def _build_ui(self):
        # 2-Column Split: Left = Menu Catalog, Right = Order Cart & Checkout
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left Frame: Menu Catalog
        left_frame = ttk.LabelFrame(paned, text="Menu Catalog", padding="8")
        paned.add(left_frame, weight=3)

        # Filter & Search bar
        search_bar = ttk.Frame(left_frame)
        search_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(search_bar, text="Category:").pack(side=tk.LEFT, padx=(0, 4))
        self.category_var = tk.StringVar(value="All")
        self.category_combo = ttk.Combobox(
            search_bar,
            textvariable=self.category_var,
            state="readonly",
            width=16
        )
        self.category_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self._filter_menu())

        ttk.Label(search_bar, text="Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_menu())
        search_entry = ttk.Entry(search_bar, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Menu Treeview Table
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "name", "category", "price")
        self.menu_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.menu_tree.heading("id", text="ID")
        self.menu_tree.heading("name", text="Item Name")
        self.menu_tree.heading("category", text="Category")
        self.menu_tree.heading("price", text="Price (INR)")

        self.menu_tree.column("id", width=40, anchor=tk.CENTER)
        self.menu_tree.column("name", width=220, anchor=tk.W)
        self.menu_tree.column("category", width=120, anchor=tk.W)
        self.menu_tree.column("price", width=90, anchor=tk.E)

        menu_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.menu_tree.yview)
        self.menu_tree.configure(yscrollcommand=menu_scroll.set)

        self.menu_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        menu_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.menu_tree.bind("<Double-1>", lambda e: self._add_selected_to_cart())

        # Menu Action Bar
        menu_action_frame = ttk.Frame(left_frame, padding="4 6 4 2")
        menu_action_frame.pack(fill=tk.X)

        ttk.Label(menu_action_frame, text="Quantity:").pack(side=tk.LEFT, padx=(0, 4))
        self.qty_var = tk.IntVar(value=1)
        qty_spin = ttk.Spinbox(menu_action_frame, from_=1, to=100, textvariable=self.qty_var, width=5)
        qty_spin.pack(side=tk.LEFT, padx=(0, 8))

        add_btn = ttk.Button(menu_action_frame, text="Add to Order Cart", command=self._add_selected_to_cart)
        add_btn.pack(side=tk.LEFT)

        refresh_btn = ttk.Button(menu_action_frame, text="Refresh Menu", command=self.refresh_menu)
        refresh_btn.pack(side=tk.RIGHT)

        # Right Frame: Order Cart & Checkout Panel
        right_frame = ttk.LabelFrame(paned, text="Active Order Cart", padding="8")
        paned.add(right_frame, weight=2)

        # Customer Details
        cust_frame = ttk.Frame(right_frame)
        cust_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(cust_frame, text="Phone No:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.customer_phone_var = tk.StringVar()
        ttk.Entry(cust_frame, textvariable=self.customer_phone_var, width=20).grid(row=0, column=1, sticky=tk.EW, padx=(4, 0))

        ttk.Label(cust_frame, text="Payment:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.payment_method_var = tk.StringVar(value="Cash")
        payment_combo = ttk.Combobox(
            cust_frame,
            textvariable=self.payment_method_var,
            values=["Cash", "Card", "UPI"],
            state="readonly",
            width=18
        )
        payment_combo.grid(row=1, column=1, sticky=tk.EW, padx=(4, 0))
        cust_frame.columnconfigure(1, weight=1)

        # Cart Table
        cart_frame = ttk.Frame(right_frame)
        cart_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        cart_cols = ("item", "qty", "price", "total")
        self.cart_tree = ttk.Treeview(cart_frame, columns=cart_cols, show="headings", selectmode="browse")
        self.cart_tree.heading("item", text="Item")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("price", text="Price")
        self.cart_tree.heading("total", text="Total")

        self.cart_tree.column("item", width=140, anchor=tk.W)
        self.cart_tree.column("qty", width=40, anchor=tk.CENTER)
        self.cart_tree.column("price", width=70, anchor=tk.E)
        self.cart_tree.column("total", width=70, anchor=tk.E)

        cart_scroll = ttk.Scrollbar(cart_frame, orient=tk.VERTICAL, command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=cart_scroll.set)
        self.cart_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cart_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Cart Manipulation Buttons (+, -, Remove, Clear)
        cart_btn_bar = ttk.Frame(right_frame)
        cart_btn_bar.pack(fill=tk.X, pady=4)

        ttk.Button(cart_btn_bar, text="+ Qty", width=6, command=self._increment_cart_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(cart_btn_bar, text="- Qty", width=6, command=self._decrement_cart_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(cart_btn_bar, text="Remove", command=self._remove_cart_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(cart_btn_bar, text="Clear Cart", command=self._clear_cart).pack(side=tk.RIGHT, padx=2)

        # Live Billing Calculations Summary Frame
        calc_frame = ttk.LabelFrame(right_frame, text="Billing Summary", padding="8")
        calc_frame.pack(fill=tk.X, pady=6)

        self.subtotal_lbl = ttk.Label(calc_frame, text="Subtotal: ₹0.00", font=("Segoe UI", 10))
        self.subtotal_lbl.pack(anchor=tk.E)

        self.tax_lbl = ttk.Label(calc_frame, text="GST (5.0%): ₹0.00", font=("Segoe UI", 10))
        self.tax_lbl.pack(anchor=tk.E)

        self.grand_total_lbl = ttk.Label(
            calc_frame,
            text="Grand Total: ₹0.00",
            font=("Segoe UI", 12, "bold"),
            foreground="#166534"
        )
        self.grand_total_lbl.pack(anchor=tk.E, pady=(4, 0))

        # Checkout Button
        self.checkout_btn = ttk.Button(
            right_frame,
            text="Complete Checkout & Print Bill",
            command=self._handle_checkout
        )
        self.checkout_btn.pack(fill=tk.X, ipady=8, pady=(4, 0))

    def refresh_menu(self):
        """Reloads active menu items and category filters from database."""
        try:
            self.menu_items = self.menu_service.get_active_menu()
            categories = ["All"] + self.menu_service.get_categories()
            self.category_combo["values"] = categories
            if self.category_var.get() not in categories:
                self.category_var.set("All")
            self._filter_menu()
        except Exception as ex:
            messagebox.showerror("Menu Load Error", str(ex), parent=self)

    def _filter_menu(self):
        """Filters displayed menu table by category and search keyword."""
        cat = self.category_var.get()
        kw = self.search_var.get().strip().lower()

        for row in self.menu_tree.get_children():
            self.menu_tree.delete(row)

        for item in self.menu_items:
            item_name = item.get("item_name") or item.get("name", "")
            item_cat = item.get("category", "")
            item_price = float(item.get("price", 0.0))

            if cat != "All" and item_cat != cat:
                continue
            if kw and kw not in item_name.lower():
                continue

            self.menu_tree.insert(
                "",
                tk.END,
                values=(item["item_id"], item_name, item_cat, f"{item_price:.2f}")
            )

    def _add_selected_to_cart(self):
        """Adds selected tree item to active order cart."""
        sel = self.menu_tree.selection()
        if not sel:
            messagebox.showwarning("Selection Required", "Please select a menu item to add.", parent=self)
            return

        values = self.menu_tree.item(sel[0], "values")
        item_id = int(values[0])
        item_name = values[1]
        item_price = float(values[3])
        qty = max(1, self.qty_var.get())

        self.cart.add_item(item_id=item_id, item_name=item_name, unit_price=item_price, quantity=qty)
        self.qty_var.set(1)
        self._update_cart_view()

    def _increment_cart_item(self):
        sel = self.cart_tree.selection()
        if not sel:
            return
        item_id = int(self.cart_tree.item(sel[0], "tags")[0])
        for itm in self.cart.items:
            if itm.item_id == item_id:
                self.cart.update_quantity(item_id, itm.quantity + 1)
                break
        self._update_cart_view()

    def _decrement_cart_item(self):
        sel = self.cart_tree.selection()
        if not sel:
            return
        item_id = int(self.cart_tree.item(sel[0], "tags")[0])
        for itm in self.cart.items:
            if itm.item_id == item_id:
                if itm.quantity > 1:
                    self.cart.update_quantity(item_id, itm.quantity - 1)
                else:
                    self.cart.remove_item(item_id)
                break
        self._update_cart_view()

    def _remove_cart_item(self):
        sel = self.cart_tree.selection()
        if not sel:
            return
        item_id = int(self.cart_tree.item(sel[0], "tags")[0])
        self.cart.remove_item(item_id)
        self._update_cart_view()

    def _clear_cart(self):
        if not self.cart.is_empty():
            if messagebox.askyesno("Clear Cart", "Clear all items from current order?", parent=self):
                self.cart.clear()
                self._update_cart_view()

    def _update_cart_view(self):
        """Rerenders cart table and calculates live tax & grand totals."""
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        for item in self.cart.items:
            line_tot = item.unit_price * item.quantity
            self.cart_tree.insert(
                "",
                tk.END,
                values=(item.item_name, item.quantity, f"{item.unit_price:.2f}", f"{line_tot:.2f}"),
                tags=(str(item.item_id),)
            )

        active_tax_rate = self.billing_service.get_tax_rate()
        totals = self.cart.calculate_totals(tax_rate=active_tax_rate)
        subtotal = totals["subtotal"]
        tax_amount = totals["tax_amount"]
        grand_total = totals["final_total"]
        tax_pct = active_tax_rate * 100.0

        self.subtotal_lbl.config(text=f"Subtotal: ₹{subtotal:.2f}")
        self.tax_lbl.config(text=f"GST ({tax_pct:.1f}%): ₹{tax_amount:.2f}")
        self.grand_total_lbl.config(text=f"Grand Total: ₹{grand_total:.2f}")

    def _handle_checkout(self):
        if self.cart.is_empty():
            messagebox.showwarning("Empty Cart", "Cannot checkout an empty order cart.", parent=self)
            return

        session = self.get_session()
        if not session or not session.is_authenticated():
            messagebox.showerror("Auth Error", "Active session expired. Please sign in again.", parent=self)
            return

        customer_phone = self.customer_phone_var.get().strip() or None
        payment_method = self.payment_method_var.get()

        active_tax_rate = self.billing_service.get_tax_rate()
        totals = self.cart.calculate_totals(tax_rate=active_tax_rate)
        grand_total = totals["final_total"]

        confirm = messagebox.askyesno(
            "Confirm Checkout",
            f"Process payment of ₹{grand_total:.2f} via {payment_method}?",
            parent=self
        )
        if not confirm:
            return

        try:
            success, bill_summary, msg = self.billing_service.checkout(
                session=session,
                cart=self.cart,
                payment_mode=payment_method,
                customer_phone_input=customer_phone,
                discount_input=0.0
            )

            if not success or not bill_summary:
                messagebox.showerror("Checkout Failed", f"Transaction could not be completed:\n{msg}", parent=self)
                return

            receipt_text = self.billing_service.get_receipt_text_for_bill(bill_summary["bill_id"])

            # Reset cart and inputs
            self.cart.clear()
            self.customer_phone_var.set("")
            self._update_cart_view()

            # Show thermal receipt dialog
            ReceiptDialog(self, receipt_text, bill_summary, self.export_service)

        except Exception as ex:
            messagebox.showerror("Checkout Failed", f"Transaction could not be completed:\n{str(ex)}", parent=self)
