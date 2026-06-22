/**
 * BlendBridge - Vue 3 前端应用
 * 上传 .blend → 诊断 → 修复 → 下载
 */
const { createApp, ref, computed } = Vue;

const app = createApp({
  setup() {
    // ── 状态 ──────────────────────────────────────────
    const uploadFile = ref(null);
    const uploadRef = ref(null);
    const currentStep = ref(0);
    const fixing = ref(false);
    const taskResult = ref({});
    const taskId = ref("");

    // ── 计算属性 ──────────────────────────────────────
    const baseName = computed(() => {
      if (!uploadFile.value) return "model";
      return uploadFile.value.name.replace(/\.blend$/i, "");
    });

    const downloadFileName = computed(() => {
      return `${baseName.value}_fixed.zip`;
    });

    const blendFileName = computed(() => {
      return `${baseName.value}_fixed.blend`;
    });

    // ── 方法 ──────────────────────────────────────────

    const handleFileChange = (file) => {
      uploadFile.value = file.raw;
    };

    const handleFileRemove = () => {
      uploadFile.value = null;
    };

    const formatSize = (bytes) => {
      if (!bytes || bytes === 0) return "—";
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    };

    const startFix = async () => {
      if (!uploadFile.value) return;

      fixing.value = true;
      currentStep.value = 1;

      const formData = new FormData();
      formData.append("file", uploadFile.value);

      try {
        const resp = await fetch("/api/upload", {
          method: "POST",
          body: formData,
        });

        const result = await resp.json();

        if (!resp.ok) {
          taskResult.value = {
            status: "error",
            error: result.error || "服务器错误",
          };
          currentStep.value = 2;
          return;
        }

        taskResult.value = result;
        taskId.value = result.task_id || "";
        currentStep.value = 2;
      } catch (err) {
        taskResult.value = {
          status: "error",
          error: "网络错误: " + err.message,
        };
        currentStep.value = 2;
      } finally {
        fixing.value = false;
      }
    };

    const _triggerDownload = (url, filename) => {
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };

    const downloadResult = () => {
      if (!taskId.value) return;
      _triggerDownload(`/api/download/${taskId.value}`, downloadFileName.value);
    };

    const downloadBlend = () => {
      if (!taskId.value) return;
      _triggerDownload(
        `/api/download/${taskId.value}/blend`,
        blendFileName.value
      );
    };

    const resetAll = () => {
      uploadFile.value = null;
      uploadRef.value?.clearFiles();
      currentStep.value = 0;
      fixing.value = false;
      taskResult.value = {};
      taskId.value = "";
    };

    return {
      uploadFile,
      uploadRef,
      currentStep,
      fixing,
      taskResult,
      taskId,
      baseName,
      downloadFileName,
      blendFileName,
      handleFileChange,
      handleFileRemove,
      startFix,
      downloadResult,
      downloadBlend,
      resetAll,
      formatSize,
    };
  },
});

app.use(ElementPlus);
app.mount("#app");
