async function copyShortsPrompt() {
    try {
        const response = await fetch(`/api/shorts/prompt/${state.videoId}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail);
        await navigator.clipboard.writeText(data.prompt);
        showToast("Đã copy prompt Short và transcript có ID!");
    } catch (error) { showToast(error.message); }
}
