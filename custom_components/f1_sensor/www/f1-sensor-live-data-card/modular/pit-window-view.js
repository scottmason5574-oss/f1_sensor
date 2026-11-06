const version = new URL(import.meta.url).searchParams.get('v');
const load = path => import(`${path}${version ? `?v=${encodeURIComponent(version)}` : ''}`);
const [{ LitElement, html, css }, { sharedStyles }, { pitWindowPresentation, seconds }] = await Promise.all([
 load('../f1-lit-3.3.2.js'), load('./view.js'), load('./pit-window-presentation.js'),
]);
export class F1PitWindowView extends LitElement {
 static properties = { result: { attribute: false }, identities: { attribute: false }, selectedId: { attribute: false } };
 static styles = [sharedStyles, css`
 :host{--pit-muted:var(--f1-muted,#b9c1ce);display:block;color:var(--f1-text,#e9edf3);font-variant-numeric:tabular-nums}
 *{box-sizing:border-box} article{padding:clamp(14px,3vw,28px);border:1px solid var(--f1-border,#425163);border-radius:16px;background:var(--f1-surface,#111d2b)}
 .eyebrow{color:var(--pit-muted);letter-spacing:.12em;font-size:.75rem;font-weight:700} h2{font-size:1.5rem;margin:10px 0 4px} p{margin:6px 0;overflow-wrap:anywhere}.muted{color:var(--pit-muted)}
 .summary{display:flex;flex-wrap:wrap;align-items:center;gap:8px 24px;margin:20px 0;padding:14px 0;border-block:1px solid var(--f1-divider,#344252)} .slot{font-size:1.3rem;font-weight:750}.badge{border:1px dashed currentColor;border-radius:5px;padding:3px 8px;font-size:.8rem}
 .axis,.row{display:grid;grid-template-columns:minmax(90px,130px) minmax(0,1fr);gap:12px}.axis{margin:24px 0 8px;font-size:.75rem;color:var(--pit-muted)}.ticks{display:flex;justify-content:space-between;border-bottom:1px solid var(--f1-divider,#526071);padding-bottom:8px;gap:4px}.ticks span{white-space:nowrap}
 .row{padding:10px 0;align-items:center;border-bottom:1px solid var(--f1-divider,#344252)}button{width:100%;min-height:48px;text-align:left;font:inherit;color:inherit;border:1px solid var(--f1-border,#526071);background:transparent;display:flex;align-items:center;gap:8px;padding:8px;border-radius:8px}button[aria-pressed=true]{border:2px solid var(--f1-focus,#78bfff)}button:focus-visible{outline:3px solid var(--f1-focus,#78bfff);outline-offset:3px}.swatch{width:4px;height:28px;flex-shrink:0;background:var(--team)}small{display:block;font-size:.7rem;color:var(--pit-muted)}
 .lane{position:relative;height:30px;background:repeating-linear-gradient(90deg,transparent 0,transparent calc(25% - 1px),var(--f1-divider,#344252) 25%);border-bottom:1px solid var(--f1-border,#526071)}.range{position:absolute;top:8px;height:14px;min-width:3px;border:2px solid currentColor;background:repeating-linear-gradient(135deg,transparent 0,transparent 3px,currentColor 4px,currentColor 5px)}.point{position:absolute;top:6px;width:4px;height:20px;background:currentColor;transform:translateX(-2px)}.detail{font-size:.75rem;color:var(--pit-muted);margin-top:5px}.selected .range{height:20px;top:5px}.selected .point{outline:2px solid currentColor;outline-offset:2px}.foot{font-size:.8rem;margin-top:20px}.unavailable{padding:14px;border:1px dashed var(--f1-border,#526071);border-radius:8px;margin-block:12px}
 @media(max-width:420px){.row,.axis{grid-template-columns:90px minmax(0,1fr);gap:10px}h2{font-size:1.2rem}.axis{font-size:.65rem}.detail{font-size:.7rem}article{padding:14px}.badge{font-size:.7rem}}
 @media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
 @media(forced-colors:active){.range,.lane,.row{border-color:CanvasText}.point,.swatch{background:CanvasText}button:focus-visible{outline-color:Highlight}}
 `];
 constructor(){super();this.result=null;this.identities={};this.selectedId=null;}
 selectDriver(id){this.dispatchEvent(new CustomEvent('pit-driver-select',{detail:{driverId:id},bubbles:true,composed:true}));this.updateComplete.then(()=>[...this.renderRoot.querySelectorAll('button[data-driver]')].find(button=>button.dataset.driver===id)?.focus());}
 render(){
  const model=pitWindowPresentation(this.result,this.identities,this.selectedId);
  const x=value=>100*(value-model.axis.min)/(model.axis.max-model.axis.min);
  return html`<article aria-label="Hypothetical pit window">
   <div class="eyebrow">SYNTHETIC PREVIEW · NOT RACE DATA</div>
   <h2>Straight-line pit window</h2><p class="muted">${model.selected.name} · ${model.type}</p>
   <p class="detail">${model.horizon}</p>
   <div class="summary" role="status" aria-live="polite"><span class="slot">${model.slot}</span><span class="badge">Hypothetical · ${model.confidence}</span></div>
   <p>${model.coverage}</p><p class="detail">${model.nearest}</p>
   ${!model.supported ? html`<p class="unavailable">${model.source}. ${model.reason || ''}</p>` : html`
    <div class="axis"><span>Race-time axis</span><div class="ticks"><span>${seconds(model.axis?.min)} s</span><span>${seconds((model.axis?.min+model.axis?.max)/2)} s</span><span>${seconds(model.axis?.max)} s →</span></div></div>
    <p class="detail">Unwrapped coordinates · further right is ahead. Hatched bars show ranges; solid marks show points. Rows identify drivers, not rank order.</p>
    ${model.rows.map(row=>html`<div class="row ${row.id===model.id?'selected':''}">
     <button type="button" data-driver=${row.id} aria-label="Select ${row.name}" aria-pressed=${row.id===model.id?'true':'false'} @click=${()=>this.selectDriver(row.id)}><span class="swatch" style="--team:${row.color}" aria-hidden="true"></span><span>${row.name}<small>${row.team}</small></span></button>
     <div><div class="lane" role="img" aria-label=${row.range?`${row.name}: ${row.relation}; approximate coordinate ${seconds(row.range.min)} to ${seconds(row.range.max)} seconds; ${row.lapLabel}`:`${row.name}: unavailable comparison`}>
      ${row.range?row.range.min===row.range.max?html`<span class="point" style="left:${x(row.range.min)}%;color:${row.color}"></span>`:html`<span class="range" style="left:${x(row.range.min)}%;width:${x(row.range.max)-x(row.range.min)}%;color:${row.color}"></span>`:''}</div>
      <div class="detail">${row.relation} · ${row.lapLabel}${row.range?` · ${row.range.min===row.range.max?'Point':'Range'} ≈ ${seconds(row.range.min)}–${seconds(row.range.max)} s`:''}</div>
      ${row.gapLabel?html`<div class="detail">${row.gapLabel}</div>`:''}</div></div>`)}
   `}
   <div class="foot"><p>${model.loss} · ${model.type}</p><p>Source: ${model.source} · confidence: ${model.confidence}</p><p class="muted">No calibrated circuit loss. Slot ranges include unresolved ties. Timing labels are approximate, not measurement precision.</p></div>
  </article>`;
 }
}
if(!customElements.get('f1-pit-window-view'))customElements.define('f1-pit-window-view',F1PitWindowView);
