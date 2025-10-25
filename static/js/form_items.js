// ------------------------------------------------------------
// GrowEasy Invoice — Add/Remove Item Row Logic (Animated v1.1 Alive Edition)
// ------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  const addBtn = document.getElementById("addItemBtn");
  const itemsContainer = document.getElementById("itemsContainer");

  if (!addBtn || !itemsContainer) return;

  // 🌿 Add GrowEasy watermark dynamically (screen only)
  const wm = document.createElement("div");
  wm.id = "groweasy-watermark";
  wm.textContent = "🌿 GrowEasy Invoice";
  document.body.appendChild(wm);

  // Inject animation & toast styles
  const style = document.createElement("style");
  style.textContent = `
    .groweasy-glow{box-shadow:0 0 12px rgba(40,167,69,0.5);animation:pulse 2s infinite;}
    @keyframes pulse{0%{box-shadow:0 0 0 rgba(40,167,69,0.4);}50%{box-shadow:0 0 15px rgba(40,167,69,0.8);}100%{box-shadow:0 0 0 rgba(40,167,69,0.4);}}
    .item-row{opacity:0;transform:translateY(-5px);transition:opacity .3s,transform .3s;}
    .item-row.show{opacity:1;transform:translateY(0);}
    .fade-out{opacity:0!important;transform:translateY(5px)!important;}
    .toast-msg{position:fixed;bottom:15px;right:20px;background:#28a745;color:#fff;padding:10px 18px;border-radius:6px;font-size:.9rem;opacity:0;transform:translateY(10px);transition:all .4s;z-index:1050;}
    .toast-msg.show{opacity:1;transform:translateY(0);}
  `;
  document.head.appendChild(style);

  const showToast = (text, color="#28a745")=>{
    const t=document.createElement("div");
    t.className="toast-msg";t.textContent=text;t.style.background=color;
    document.body.appendChild(t);
    setTimeout(()=>t.classList.add("show"),10);
    setTimeout(()=>{t.classList.remove("show");setTimeout(()=>t.remove(),500);},1800);
  };

  const createItemRow=(name="",qty="",price="")=>{
    const r=document.createElement("div");
    r.className="row g-2 align-items-end mb-2 item-row";
    r.innerHTML=`
      <div class="col-md-5"><input type="text" name="item_name[]" class="form-control" placeholder="Item name" value="${name}"></div>
      <div class="col-md-2"><input type="number" step="1" name="item_qty[]" class="form-control" placeholder="Qty" value="${qty}"></div>
      <div class="col-md-3"><input type="number" step="0.01" name="item_price[]" class="form-control" placeholder="Price" value="${price}"></div>
      <div class="col-md-2 text-end">
        <button type="button" class="btn btn-outline-danger btn-sm removeItemBtn"><strong>−</strong></button>
      </div>`;
    return r;
  };

  if(itemsContainer.children.length===0){
    const f=createItemRow();itemsContainer.appendChild(f);
    setTimeout(()=>f.classList.add("show"),10);
  }

  addBtn.classList.add("groweasy-glow");
  addBtn.addEventListener("click",()=>{
    const n=createItemRow();
    itemsContainer.appendChild(n);
    setTimeout(()=>n.classList.add("show"),10);
    showToast("🌿 Item added!");
  });

  itemsContainer.addEventListener("click",(e)=>{
    if(e.target.closest(".removeItemBtn")){
      const r=e.target.closest(".item-row");
      if(r&&itemsContainer.children.length>1){
        r.classList.add("fade-out");
        setTimeout(()=>r.remove(),300);
        showToast("🗑️ Item removed!","#dc3545");
      }else{showToast("⚠️ At least one item required.","#ffc107");}
    }
  });
});