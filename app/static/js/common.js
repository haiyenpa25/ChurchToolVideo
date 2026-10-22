// Shared requests, text templates and defaults used by the clip editor.
function shortsEscape(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
}
async function shortsRequest(url, options) {
    const response = await fetch(url, options);
    if (response.status === 401) document.getElementById("loginOverlay")?.classList.remove("hidden");
    if(!/application\/(?:[a-z0-9.+-]*\+)?json/i.test(response.headers.get("content-type") || "")) throw new Error(`Máy chủ lỗi (HTTP ${response.status})`);
    const data = await response.json();
    if (!response.ok) { const error=new Error(typeof data.detail === "string" ? data.detail : "Dữ liệu chưa hợp lệ. Hãy kiểm tra mốc thời gian."); error.status=response.status; throw error; }
    return data;
}
function captionTemplate(id) {
    return captionPreview.templates.find(t => t.id === (id ?? sharedCaptionStyle())) || captionPreview.templates[0];
}
const CAPTION_ANIMATIONS = [["auto", "Theo mẫu"], ["none", "Không"], ["fade", "Mờ dần"], ["pop", "Phóng to"],
                            ["slide", "Trượt lên"], ["typewriter", "Từng chữ"]];
const CAPTION_BOXES = [["auto", "Theo mẫu"], ["none", "Không nền"], ["dark", "Hộp đen mờ"], ["solid", "Hộp đen đặc"]];
function sharedCaptionStyle() { return state.shortCaptionStyle || "pop"; }
function sharedCaptionPosition() { return state.shortCaptionPosition || "bottom"; }
function defaultCaptionY(aspect=previewAspect()) { return 1-(aspect==="9:16" ? 0.35 : 0.08); }
