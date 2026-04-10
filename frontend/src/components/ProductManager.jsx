import { useState, useEffect } from "react";
import { getProducts, addProduct, deleteProduct } from "../api";

export default function ProductManager() {
  const [products, setProducts] = useState([]);
  const [form, setForm]         = useState({ name: "", price: "", supplier_cost: "", unit: "units" });
  const [error, setError]       = useState(null);
  const [success, setSuccess]   = useState(null);
  const [loading, setLoading]   = useState(false);

  const fetchProducts = async () => {
    try {
      const res = await getProducts();
      setProducts(res.data);
    } catch { setError("Could not load products."); }
  };

  useEffect(() => { fetchProducts(); }, []);

  const handleAdd = async () => {
    setError(null); setSuccess(null);
    if (!form.name || !form.price || !form.supplier_cost) {
      setError("All fields are required."); return;
    }
    setLoading(true);
    try {
      await addProduct({
      name: form.name,
      price: parseFloat(form.price),
      supplier_cost: parseFloat(form.supplier_cost),
      unit: form.unit || "units"
      });

      setSuccess(`"${form.name}" added successfully.`);
      setError("");

      setTimeout(() => {
      setSuccess("");
      }, 3000);

      setForm({ name: "", price: "", supplier_cost: "", unit: "units" });
      fetchProducts();

    } catch (e) {
      setError(e.response?.data?.detail || "Failed to add product.");
      setSuccess("");

      setTimeout(() => {
      setError("");
      }, 3000);
    }

setLoading(false);

  const handleDelete = async (name) => {
    if (!window.confirm(`Delete "${name}" and all its sales data?`)) return;
    try {
      await deleteProduct(name);
      fetchProducts();
    } catch { setError("Failed to delete product."); }
  };

  return (
    <div>
      {/* Add product form */}
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h2 className="card-title">Add New Product</h2>
        <p className="card-subtitle">Register a product once — reuse it every day in Daily Entry</p>

        <div className="form-grid">
          <div className="field">
            <label>Product Name</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Amul Butter 500g" />
          </div>
          <div className="field">
            <label>Unit</label>
            <input value={form.unit} onChange={e => setForm({ ...form, unit: e.target.value })}
              placeholder="e.g. kg, packet, bottle" />
          </div>
          <div className="field">
            <label>Selling Price (₹)</label>
            <input type="number" value={form.price}
              onChange={e => setForm({ ...form, price: e.target.value })} placeholder="e.g. 50" />
          </div>
          <div className="field">
            <label>Supplier Cost (₹)</label>
            <input type="number" value={form.supplier_cost}
              onChange={e => setForm({ ...form, supplier_cost: e.target.value })} placeholder="e.g. 38" />
          </div>
        </div>

        {error   && <p className="msg-error">{error}</p>}
        {success && <p className="msg-success">{success}</p>}

        <button className="btn-primary" onClick={handleAdd} disabled={loading}>
          {loading ? "Adding..." : "Add Product"}
        </button>
      </div>

      {/* Product list */}
      <div className="card">
        <h2 className="card-title">Your Products</h2>
        <p className="card-subtitle">{products.length} product{products.length !== 1 ? "s" : ""} registered</p>

        {products.length === 0 ? (
          <p style={{ color: "#999", fontSize: "14px", marginTop: "1rem" }}>
            No products yet. Add one above to get started.
          </p>
        ) : (
          <div className="product-list">
            {products.map((p) => (
              <div className="product-row" key={p.name}>
                <div>
                  <p className="product-name">{p.name}</p>
                  <p className="product-meta">
                    Price: ₹{p.price} &nbsp;·&nbsp; Cost: ₹{p.supplier_cost}
                    &nbsp;·&nbsp; Margin: ₹{(p.price - p.supplier_cost).toFixed(2)}
                    &nbsp;·&nbsp; Unit: {p.unit}
                  </p>
                </div>
                <button className="btn-delete" onClick={() => handleDelete(p.name)}>Delete</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}