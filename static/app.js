/**
 * BlendBridge - Vue 3 前端应用
 * 上传 .blend → 诊断 → 修复 → 下载
 */
const { createApp, ref, computed } = Vue;

const app = createApp({
  setup() {
    // ── 状态 ──────────────────────────────────────────
    const uploadFile = ref(null);        // 当前上传的文件
    const uploadRef = ref(null);         // el-upload 引用
    const currentStep = ref(0);          // 当前步骤 0-3
    const fixing = ref(false);           // 是否正在修复
    const taskResult = ref({});           // 后端返回结果
    const taskId = ref("");              // 任务 ID

    // ── 计算属性 ──────────────────────────────────────
    const downloadFileName = computed(() => {
      if (!uploadFile.value) return "result.zip";
      const name = uploadFile.value.name.replace(/\.blend$/i, "");
      return `${name}_fixed.zip`;
    });

    // ── 方法 ──────────────────────────────────────────

    /** 文件选择变化 */
    const handleFileChange = (file) => {
      uploadFile.value = file.raw;
    };

    /** 移除文件 */
    const handleFileRemove = () => {
      uploadFile.value = null;
    };

    /** 格式化文件大小 */
    const formatSize = (bytes) => {
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    };

    /** 开始修复流程 */
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
          error: `网络错误: ${err.message}`,
        };
        currentStep.value = 2;
      } finally {
        fixing.value = false;
      }
    };

    /** 下载修复结果 */
    const downloadResult = () => {
      if (!taskId.value) return;

      const link = document.createElement("a");
      link.href = `/api/download/${taskId.value}`;
      link.download = downloadFileName.value;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };

    /** 全部重置 */
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
      downloadFileName,
      handleFileChange,
      handleFileRemove,
      startFix,
      downloadResult,
      resetAll,
      formatSize,
    };
  },
});

// 注册 Element Plus 图标
app.use(ElementPlus);
app.mount("#app");
