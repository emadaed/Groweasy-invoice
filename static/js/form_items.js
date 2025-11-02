// form_items.js v3 - single handler enforced
document.addEventListener('DOMContentLoaded', function(){
  const addBtn = document.getElementById('addItemBtn');
  const itemsContainer = document.getElementById('itemsContainer');
  if (!addBtn || !itemsContainer) return;

  function createRow(){
    const row = document.createElement('div');
    row.className = 'row g-2 align-items-end mb-2 item-row';
    row.innerHTML = `
      <div class="col-md-6"><input type="text" name="item_name[]" class="form-control" placeholder="Item name" required></div>
      <div class="col-md-3"><input type="number" name="item_qty[]" class="form-control" placeholder="Qty" required min="1"></div>
      <div class="col-md-2"><input type="number" name="item_price[]" class="form-control" placeholder="Price" required min="0"></div>
      <div class="col-md-1 text-end"><button type="button" class="btn btn-light removeItemBtn" title="Remove">&times;</button></div>
    `;
    return row;
  }

  // remove any existing inline handlers
  addBtn.onclick = null;

  addBtn.addEventListener('click', function(e){
    e.preventDefault();
    const newRow = createRow();
    newRow.style.opacity = 0;
    itemsContainer.appendChild(newRow);
    requestAnimationFrame(()=>{ newRow.style.transition='opacity .22s ease, transform .22s ease'; newRow.style.opacity=1; });
    if (typeof window.showToast === 'function') window.showToast('🌿 Item added!');
  });

  itemsContainer.addEventListener('click', function(e){
    const btn = e.target.closest('.removeItemBtn');
    if (!btn) return;
    const row = btn.closest('.item-row');
    if (!row) return;
    if (itemsContainer.children.length <= 1){
      if (typeof window.showToast === 'function') window.showToast('⚠️ At least one item required.','#ffc107');
      return;
    }
    row.style.transition='opacity .22s ease, transform .22s ease';
    row.style.opacity = 0; row.style.transform='translateY(-6px)';
    setTimeout(()=> row.remove(), 260);
    if (typeof window.showToast === 'function') window.showToast('🗑️ Item removed!','#dc3545');
  });
});