<template>
  <div class="publish-center">
    <section class="account-dock">
      <div class="dock-head">
        <div>
          <h2>账号主体</h2>
        </div>
        <div class="dock-actions">
          <el-tag v-if="selectedProfileGroup" type="info" round>
            {{ selectedProfileGroup.normalCount }} 个可用平台
          </el-tag>
          <el-button @click="resetForm">清空</el-button>
        </div>
      </div>

      <div v-if="accountGroups.length" class="account-dock-body">
        <div class="account-rail">
          <button
            v-for="group in accountGroups"
            :key="group.name"
            type="button"
            :class="['account-pill', { active: publishForm.selectedProfileName === group.name }]"
            @click="selectProfile(group)"
          >
            <span class="profile-avatar">
              <img v-if="group.avatarUrl" :src="resolveAvatarUrl(group.avatarUrl)" alt="" />
              <span v-else>{{ group.name.slice(0, 1) }}</span>
            </span>
            <span class="profile-meta">
              <strong>{{ group.name }}</strong>
              <small>{{ group.accounts.length }} 个平台，{{ group.normalCount }} 个正常</small>
            </span>
          </button>
        </div>
        <div v-if="selectedProfileGroup" class="platform-picker">
          <label
            v-for="account in selectedProfileGroup.accounts"
            :key="account.id"
            :class="['platform-card', { disabled: account.status !== '正常' }]"
          >
            <el-checkbox
              v-model="publishForm.selectedPlatformTypes"
              :label="Number(account.type)"
              :disabled="account.status !== '正常'"
            >
              <span :class="['platform-badge', `platform-badge--${platformByType(account.type).iconClass}`]">
                <img :src="platformByType(account.type).iconSrc" :alt="`${platformByType(account.type).name} 图标`" />
              </span>
              <span class="platform-info">
                <strong>{{ platformByType(account.type).name }}</strong>
                <small>{{ account.name || account.filePath }}</small>
              </span>
              <el-tag :type="account.status === '正常' ? 'success' : 'danger'" size="small" round>
                {{ account.status }}
              </el-tag>
            </el-checkbox>
          </label>
        </div>
      </div>
      <el-empty v-else description="暂无可发布账号，请先到账号管理绑定平台账号" />
    </section>

    <main class="workspace-grid">
      <section class="panel media-panel">
        <div class="section-head">
          <div>
            <h3>发布素材</h3>
          </div>
        </div>

        <el-upload
          class="drop-upload"
          :class="{ 'has-files': publishForm.fileList.length }"
          drag
          multiple
          accept="video/*"
          :action="`${apiBaseUrl}/upload`"
          :headers="authHeaders"
          :auto-upload="true"
          :show-file-list="false"
          :on-success="handleVideoUploadSuccess"
          :on-error="handleUploadError"
        >
          <div v-if="!publishForm.fileList.length" class="drop-empty-state">
            <el-icon class="drop-icon"><UploadFilled /></el-icon>
            <div class="drop-title">拖拽视频到这里</div>
            <div class="drop-subtitle">支持 mp4 / mov / webm 等常见视频格式</div>
            <el-button class="drop-library-button" @click.stop="openVideoLibrary">
              <el-icon><FolderOpened /></el-icon>
              从素材库选择
            </el-button>
          </div>
          <div v-else class="video-file-list">
            <div v-for="(file, index) in publishForm.fileList" :key="`${file.path}-${index}`" class="video-file-row">
              <span class="video-file-index">{{ index + 1 }}</span>
              <div class="video-file-copy">
                <strong :title="file.name">{{ file.name }}</strong>
                <small>{{ (file.size / 1024 / 1024).toFixed(2) }}MB</small>
              </div>
              <el-button size="small" type="danger" plain @click.stop="removeVideo(index)">移除</el-button>
            </div>
            <div class="video-drop-hint">
              <span>继续拖拽添加视频</span>
              <el-button size="small" @click.stop="openVideoLibrary">
                <el-icon><FolderOpened /></el-icon>
                素材库
              </el-button>
            </div>
          </div>
        </el-upload>
      </section>

      <section class="panel cover-panel">
        <div class="section-head">
          <div>
            <h3>平台封面</h3>
          </div>
        </div>

        <div class="cover-layout">
          <div
            v-for="spec in coverDisplaySpecs"
            :key="spec.ratio"
            :class="['cover-card', { 'is-inactive': !spec.active }]"
          >
            <div class="cover-spec">
              <span>{{ spec.active ? spec.platformNames.join(' / ') : '当前平台暂不需要' }}</span>
              <strong>{{ spec.ratio }}</strong>
            </div>
            <div class="cover-stage">
              <el-upload
                :class="['cover-drop', spec.ratioClass]"
                drag
                accept="image/*"
                :disabled="!spec.active"
                :action="`${apiBaseUrl}/upload`"
                :headers="authHeaders"
                :auto-upload="true"
                :show-file-list="false"
                :on-success="(response, file) => handleCoverUploaded(spec.ratio, response, file)"
                :on-error="handleCoverUploadError"
              >
                <div
                  v-if="spec.active && publishForm.coverVariants[spec.ratio]"
                  class="cover-thumb"
                >
                  <img
                    :src="publishForm.coverVariants[spec.ratio].url"
                    :alt="publishForm.coverVariants[spec.ratio].name"
                  />
                </div>
                <div v-else class="cover-empty">
                  <el-icon class="cover-empty-icon"><UploadFilled /></el-icon>
                  <span>{{ spec.active ? `${spec.ratio} 封面` : '无需上传' }}</span>
                </div>
              </el-upload>
            </div>
            <div class="cover-tools">
              <el-button size="small" :disabled="!spec.active" @click="openCoverLibrary(spec.ratio)">素材库</el-button>
              <el-button
                v-if="spec.active && publishForm.coverVariants[spec.ratio]"
                size="small"
                type="danger"
                plain
                @click="removeCoverVariant(spec.ratio)"
              >
                移除
              </el-button>
            </div>
          </div>
        </div>
      </section>

      <section class="panel content-panel">
        <div class="section-head">
          <div>
            <h3>发布内容</h3>
          </div>
          <el-tag type="info" round>{{ titleLimitHint }} · {{ topicLimitHint }}</el-tag>
        </div>

        <el-form label-position="top" @submit.prevent>
          <el-form-item label="作品标题" required>
            <el-input
              v-model="publishForm.title"
              maxlength="20"
              show-word-limit
              clearable
              placeholder="抖音 / 小红书 / B站共用，最多20字"
            />
          </el-form-item>

          <el-form-item label="作品文案">
            <el-input
              v-model="publishForm.description"
              class="title-textarea"
              type="textarea"
              :rows="3"
              clearable
              resize="none"
              placeholder="可选。这里填写作品简介/正文，与上面的标题相互独立"
            />
          </el-form-item>

          <el-form-item label="话题">
            <div class="topic-editor">
              <div class="topic-tags">
                <el-tag
                  v-for="topic in publishForm.selectedTopics"
                  :key="topic"
                  closable
                  round
                  @close="removeTopic(topic)"
                >
                  #{{ topic }}
                </el-tag>
                <span v-if="!publishForm.selectedTopics.length" class="topic-placeholder">
                  暂无话题
                </span>
              </div>
              <div class="topic-input-row">
                <el-input
                  v-model="publishForm.topicDraft"
                  clearable
                  placeholder="输入话题后回车添加"
                  @keydown.enter.prevent="addTopic"
                />
                <el-button native-type="button" @click="addTopic">添加</el-button>
              </div>
            </div>
          </el-form-item>

          <div v-if="hasBilibili" class="bili-settings-inline">
            <div class="bili-settings-inline__head">
              <h4>B站设置</h4>
              <span>仅用于B站发布</span>
            </div>
            <div class="form-grid">
              <el-form-item label="类型" required>
                <el-radio-group v-model="publishForm.biliType">
                  <el-radio label="自制">自制</el-radio>
                  <el-radio label="转载">转载</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="分区" required>
                <el-select v-model="publishForm.biliPartition" filterable clearable placeholder="请选择分区">
                  <el-option
                    v-for="partition in biliPartitions"
                    :key="partition"
                    :label="partition"
                    :value="partition"
                  />
                </el-select>
              </el-form-item>
            </div>
          </div>
        </el-form>
      </section>

      <section v-if="selectedPlatformAccounts.length" class="panel schedule-panel">
        <div class="section-head">
          <div>
            <h3>发布方式</h3>
          </div>
        </div>
        <ScheduleSettings
          v-model:schedule-enabled="publishForm.scheduleEnabled"
          v-model:videos-per-day="publishForm.videosPerDay"
          v-model:daily-times="publishForm.dailyTimes"
          v-model:start-days="publishForm.startDays"
          v-model:time-jitter-minutes="publishForm.timeJitterMinutes"
        />
      </section>
    </main>

    <section v-if="publishTask" class="panel publish-progress-panel">
      <div class="publish-progress-head">
        <div>
          <div class="publish-progress-title-row">
            <h3>发布进度</h3>
            <el-tag :type="taskStatusTagType" round>{{ taskStatusLabel }}</el-tag>
          </div>
          <p>{{ publishTask.message || '正在处理发布任务' }}</p>
        </div>
        <div class="publish-progress-summary">
          <strong>{{ taskOverallProgress }}%</strong>
          <span>已用时 {{ formatElapsed(publishTask.startedAt, publishTask.finishedAt) }}</span>
        </div>
      </div>

      <el-progress
        class="publish-overall-progress"
        :percentage="taskOverallProgress"
        :status="taskProgressStatus"
        :stroke-width="12"
      />

      <div class="platform-progress-list">
        <article
          v-for="platform in publishTask.platforms || []"
          :key="platform.type"
          :class="['platform-progress-item', `is-${platform.status || 'queued'}`]"
        >
          <div class="platform-progress-icon">
            <img :src="platformByType(platform.type).iconSrc" :alt="platform.name" />
          </div>
          <div class="platform-progress-main">
            <div class="platform-progress-row">
              <div>
                <strong>{{ platform.name || platformByType(platform.type).name }}</strong>
                <span>{{ platformStageLabel(platform) }}</span>
              </div>
              <div class="platform-progress-meta">
                <span v-if="platform.uploadPercent !== null && platform.uploadPercent !== undefined">
                  视频 {{ platform.uploadPercent }}%
                </span>
                <span>{{ formatElapsed(platform.startedAt, platform.finishedAt) }}</span>
              </div>
            </div>
            <el-progress
              :percentage="Number(platform.progress || 0)"
              :status="platformProgressStatus(platform.status)"
              :stroke-width="8"
              :show-text="false"
            />
            <div class="platform-current-step">{{ platformCurrentStepText(platform) }}</div>
            <ol class="platform-step-list">
              <li
                v-for="(step, index) in publishSteps"
                :key="step.stage"
                :class="platformStepClass(platform, index)"
              >
                <span class="platform-step-dot">
                  {{ platformStepClass(platform, index).complete ? '✓' : (platformStepClass(platform, index).skipped ? '—' : index + 1) }}
                </span>
                <span class="platform-step-name">{{ step.label }}</span>
              </li>
            </ol>
            <p>{{ platform.message || '等待开始' }}</p>
          </div>
        </article>
      </div>
    </section>

    <section class="publish-action-bar">
      <div class="publish-action-copy">
        <strong>{{ debugDryRunEnabled ? '预发布检查' : '准备发布' }}</strong>
        <span>
          已选择 {{ selectedPlatformAccounts.length || 0 }} 个平台 ·
          {{ publishForm.fileList.length || 0 }} 个视频 ·
          {{ debugDryRunEnabled ? '停在最终发布前' : (publishForm.scheduleEnabled ? '定时发布' : '立即发布') }}
        </span>
      </div>
      <div class="publish-action-buttons">
        <el-button
          v-if="publishing"
          type="danger"
          plain
          size="large"
          :loading="stoppingPublish"
          @click="stopCurrentPublishTask"
        >
          {{ stoppingPublish ? '正在停止' : '停止发布' }}
        </el-button>
        <el-button type="primary" size="large" :loading="publishing || accountChecking" @click="confirmPublish">
          {{ publishing ? '发布进行中' : (accountChecking ? '检测账号中' : (debugDryRunEnabled ? '预发布检查' : '发布到')) }} {{ selectedPlatformAccounts.length || 0 }} 个平台
        </el-button>
      </div>
    </section>

    <el-alert
      v-if="publishStatus"
      class="floating-status"
      :title="publishStatus.message"
      :type="publishStatus.type"
      show-icon
      :closable="true"
      @close="publishStatus = null"
    />

    <el-dialog v-model="videoLibraryVisible" title="选择视频素材" width="820px">
      <div class="library-content">
        <el-empty v-if="videoMaterials.length === 0" description="暂无视频文件" />
        <el-checkbox-group v-else v-model="selectedVideoMaterialIds">
          <div class="material-list">
            <div v-for="material in videoMaterials" :key="material.id" class="material-item">
              <el-checkbox :label="material.id">
                <div class="material-info">
                  <strong>{{ material.filename }}</strong>
                  <small>{{ material.filesize }}MB · {{ material.upload_time }}</small>
                </div>
              </el-checkbox>
            </div>
          </div>
        </el-checkbox-group>
      </div>
      <template #footer>
        <el-button @click="videoLibraryVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmVideoSelection">添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="coverLibraryVisible" title="选择封面素材" width="820px">
      <div class="library-content">
        <el-empty v-if="imageMaterials.length === 0" description="暂无图片文件" />
        <el-radio-group v-else v-model="selectedCoverMaterialId">
          <div class="material-list">
            <div v-for="material in imageMaterials" :key="material.id" class="material-item">
              <el-radio :label="material.id">
                <div class="material-info">
                  <strong>{{ material.filename }}</strong>
                  <small>{{ material.filesize }}MB · {{ material.upload_time }}</small>
                </div>
              </el-radio>
            </div>
          </div>
        </el-radio-group>
      </div>
      <template #footer>
        <el-button @click="coverLibraryVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCoverSelection">使用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FolderOpened, UploadFilled } from '@element-plus/icons-vue'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'
import { accountApi } from '@/api/account'
import { materialApi } from '@/api/material'
import { getPlatformConfig } from '@/utils/platformConfig'
import { validatePublishForm } from '@/utils/formValidation'
import ScheduleSettings from '@/components/publish/ScheduleSettings.vue'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
const debugDryRunEnabled = false
const GLOBAL_TOPIC_LIMIT = 5
const authHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token') || ''}`
}))

const accountStore = useAccountStore()
const appStore = useAppStore()
const materials = computed(() => appStore.materials)

const platformCatalog = [
  { type: 3, name: '抖音', iconSrc: '/platform-icons/douyin.ico', iconClass: 'douyin', color: '#111827' },
  { type: 2, name: '视频号', iconSrc: '/platform-icons/wechat-channels-logo.png', iconClass: 'channels', color: '#ff9f2f' },
  { type: 5, name: 'B站', iconSrc: '/platform-icons/bilibili.png', iconClass: 'bilibili', color: '#00a1d6' },
  { type: 1, name: '小红书', iconSrc: '/platform-icons/xiaohongshu.png', iconClass: 'xhs', color: '#ff2442' },
  { type: 4, name: '快手', iconSrc: '/platform-icons/kuaishou.ico', iconClass: 'kuaishou', color: '#ff8a00' }
]

const platformOrder = platformCatalog.reduce((order, platform, index) => {
  order[platform.type] = index
  return order
}, {})

const coverSpecs = {
  '3:4': { ratio: '3:4', cssRatio: '3 / 4' },
  '4:3': { ratio: '4:3', cssRatio: '4 / 3' },
  '16:9': { ratio: '16:9', cssRatio: '16 / 9' }
}

const platformCoverRatios = {
  1: ['4:3'],
  2: ['3:4', '4:3'],
  3: ['3:4', '4:3'],
  4: ['3:4', '4:3'],
  5: ['4:3', '16:9']
}

const biliPartitions = [
  '影视', '娱乐', '音乐', '舞蹈', '动画', '绘画', '鬼畜', '游戏', '资讯', '知识',
  '人工智能', '科技数码', '汽车', '时尚美妆', '家装房产', '户外潮流', '健身',
  '体育运动', '手工', '美食', '小剧场', '旅游出行', '三农', '动物', '亲子',
  '健康', '情感', 'vlog', '生活兴趣', '生活经验'
]

const publishFormDefaults = {
  selectedProfileName: '',
  selectedPlatformTypes: [],
  fileList: [],
  title: '',
  description: '',
  selectedTopics: [],
  topicDraft: '',
  coverVariants: {},
  biliType: '自制',
  biliPartition: '',
  scheduleEnabled: false,
  timeJitterMinutes: 15,
  videosPerDay: 1,
  dailyTimes: ['10:00'],
  startDays: 0
}

const PUBLISH_DRAFT_STORAGE_KEY = 'auto-upload:publish-center:draft'
const ACTIVE_PUBLISH_TASK_STORAGE_KEY = 'auto-upload:active-publish-task'
const LAST_PUBLISH_TASK_STORAGE_KEY = 'auto-upload:last-publish-task'
const HANDLED_PUBLISH_TASK_STORAGE_KEY = 'auto-upload:handled-publish-task'

const createPublishFormDefaults = () => ({
  ...publishFormDefaults,
  selectedPlatformTypes: [],
  fileList: [],
  selectedTopics: [],
  coverVariants: {},
  dailyTimes: ['10:00']
})

const publishForm = reactive(createPublishFormDefaults())

const normalizeTopics = (topics, limit = GLOBAL_TOPIC_LIMIT) => {
  if (!Array.isArray(topics)) return []
  const seen = new Set()
  const normalized = []
  const maxCount = Math.max(0, Number(limit) || GLOBAL_TOPIC_LIMIT)
  topics.forEach(topic => {
    const text = String(topic || '').trim().replace(/^#+/, '')
    if (!text || seen.has(text) || normalized.length >= maxCount) return
    seen.add(text)
    normalized.push(text)
  })
  return normalized
}

const normalizePublishDraft = (draft) => ({
  ...createPublishFormDefaults(),
  ...(draft && typeof draft === 'object' ? draft : {}),
  // 旧版把作品文案存在 title 中；首次升级时迁移到 description，避免误当成独立标题。
  title: draft?.description === undefined ? '' : String(draft?.title || '').slice(0, 20),
  description: draft?.description === undefined ? String(draft?.title || '') : String(draft?.description || ''),
  selectedPlatformTypes: Array.isArray(draft?.selectedPlatformTypes) ? draft.selectedPlatformTypes.map(Number) : [],
  fileList: Array.isArray(draft?.fileList) ? draft.fileList : [],
  selectedTopics: normalizeTopics(draft?.selectedTopics),
  coverVariants: draft?.coverVariants && typeof draft.coverVariants === 'object' ? draft.coverVariants : {},
  dailyTimes: Array.isArray(draft?.dailyTimes) && draft.dailyTimes.length ? draft.dailyTimes : ['10:00'],
  videosPerDay: Number(draft?.videosPerDay) || 1,
  startDays: Number(draft?.startDays) || 0,
  timeJitterMinutes: Number(draft?.timeJitterMinutes ?? 15),
  scheduleEnabled: Boolean(draft?.scheduleEnabled)
})

const restorePublishDraft = () => {
  try {
    const raw = sessionStorage.getItem(PUBLISH_DRAFT_STORAGE_KEY)
    if (!raw) return
    Object.assign(publishForm, normalizePublishDraft(JSON.parse(raw)))
  } catch (error) {
    console.warn('恢复发布草稿失败', error)
    sessionStorage.removeItem(PUBLISH_DRAFT_STORAGE_KEY)
  }
}

const persistPublishDraft = () => {
  try {
    sessionStorage.setItem(PUBLISH_DRAFT_STORAGE_KEY, JSON.stringify(publishForm))
  } catch (error) {
    console.warn('保存发布草稿失败', error)
  }
}

restorePublishDraft()

const publishing = ref(false)
const stoppingPublish = ref(false)
const accountChecking = ref(false)
const publishStatus = ref(null)
const publishTask = ref(null)
const taskClock = ref(Date.now())
let publishTaskPollTimer = null
let taskClockTimer = null
const videoLibraryVisible = ref(false)
const coverLibraryVisible = ref(false)
const selectedVideoMaterialIds = ref([])
const selectedCoverMaterialId = ref(null)
const coverSelectingType = ref(null)

const terminalTaskStatuses = new Set(['success', 'partial_failure', 'failed', 'cancelled'])

const taskOverallProgress = computed(() => {
  const platforms = publishTask.value?.platforms || []
  if (!platforms.length) return 0
  const total = platforms.reduce((sum, platform) => sum + Number(platform.progress || 0), 0)
  return Math.max(0, Math.min(100, Math.round(total / platforms.length)))
})

const taskStatusLabel = computed(() => ({
  queued: '等待开始',
  running: '发布中',
  waiting_review: '等待检查',
  cancelling: '正在停止',
  cancelled: '已停止',
  success: publishTask.value?.dryRun ? '预发布完成' : '全部成功',
  partial_failure: '部分失败',
  failed: '发布失败'
}[publishTask.value?.status] || '处理中'))

const taskStatusTagType = computed(() => ({
  success: 'success',
  waiting_review: 'warning',
  cancelling: 'warning',
  cancelled: 'info',
  partial_failure: 'warning',
  failed: 'danger'
}[publishTask.value?.status] || 'info'))

const taskProgressStatus = computed(() => {
  if (publishTask.value?.status === 'success') return 'success'
  if (['partial_failure', 'failed'].includes(publishTask.value?.status)) return 'exception'
  if (['cancelling', 'cancelled'].includes(publishTask.value?.status)) return 'warning'
  return undefined
})

const publishSteps = [
  { stage: 'opening', label: '打开发布页' },
  { stage: 'uploading', label: '上传视频' },
  { stage: 'cover', label: '设置封面' },
  { stage: 'content', label: '填写内容' },
  { stage: 'scheduling', label: '设置时间' },
  { stage: 'publishing', label: '提交发布' }
]

const publishStageIndexes = {
  opening: 0,
  uploading: 1,
  retrying: 1,
  cover: 2,
  content: 3,
  scheduling: 4,
  publishing: 5,
  review: 5,
  success: 5
}

const platformStageNames = {
  queued: '等待开始',
  opening: '打开发布页',
  uploading: '上传视频',
  retrying: '自动重试',
  cover: '设置封面',
  content: '填写发布内容',
  scheduling: '设置发布时间',
  publishing: '提交发布',
  review: '等待人工检查',
  cancelling: '正在停止',
  cancelled: '已停止',
  success: '发布成功',
  failed: '发布失败'
}

const platformStageLabel = (platform) => {
  return platformStageNames[platform?.stage] || platform?.stage || '处理中'
}

const platformEffectiveStage = (platform) => {
  if (['failed', 'cancelled'].includes(platform?.stage)) {
    return platform?.lastStage || 'opening'
  }
  return platform?.stage
}

const platformStepIndex = (platform) => {
  const stage = platformEffectiveStage(platform)
  return publishStageIndexes[stage] ?? -1
}

const platformCurrentStepText = (platform) => {
  if (platform?.status === 'queued') return `等待开始 · 共 ${publishSteps.length} 步`
  const index = Math.max(0, platformStepIndex(platform))
  const label = publishSteps[index]?.label || platformStageLabel(platform)
  if (platform?.status === 'cancelled') return `已在第 ${index + 1}/${publishSteps.length} 步停止 · ${label}`
  if (platform?.status === 'cancelling') return `正在停止 · 第 ${index + 1}/${publishSteps.length} 步 · ${label}`
  if (platform?.status === 'failed') return `第 ${index + 1}/${publishSteps.length} 步失败 · ${label}`
  if (platform?.status === 'success') return `${publishSteps.length}/${publishSteps.length} 步已全部完成`
  return `当前第 ${index + 1}/${publishSteps.length} 步 · ${platformStageLabel(platform)}`
}

const platformStepClass = (platform, index) => {
  const current = platformStepIndex(platform)
  const terminalSuccess = platform?.status === 'success'
  const isSkippedSchedule = index === 4 && platform?.scheduleEnabled === false && current > 4
  return {
    complete: !isSkippedSchedule && (terminalSuccess || index < current),
    active: index === current && !['success', 'failed', 'cancelled'].includes(platform?.status),
    failed: index === current && platform?.status === 'failed',
    cancelled: index === current && platform?.status === 'cancelled',
    skipped: isSkippedSchedule,
    pending: index > current || current < 0
  }
}

const platformProgressStatus = (status) => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'exception'
  if (['review', 'cancelling', 'cancelled'].includes(status)) return 'warning'
  return undefined
}

const formatElapsed = (startedAt, finishedAt) => {
  if (!startedAt) return '0秒'
  const end = finishedAt || taskClock.value
  const seconds = Math.max(0, Math.floor((end - startedAt) / 1000))
  if (seconds < 60) return `${seconds}秒`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${minutes}分${rest}秒`
}

const persistPublishTask = (task) => {
  if (!task?.id) return
  publishTask.value = task
  localStorage.setItem(LAST_PUBLISH_TASK_STORAGE_KEY, JSON.stringify(task))
  if (terminalTaskStatuses.has(task.status)) {
    localStorage.removeItem(ACTIVE_PUBLISH_TASK_STORAGE_KEY)
  } else {
    localStorage.setItem(ACTIVE_PUBLISH_TASK_STORAGE_KEY, task.id)
  }
}

const stopPublishTaskPolling = () => {
  if (publishTaskPollTimer) {
    clearTimeout(publishTaskPollTimer)
    publishTaskPollTimer = null
  }
}

const handlePublishTaskFinished = (task) => {
  publishing.value = false
  stopPublishTaskPolling()
  const handledTaskId = localStorage.getItem(HANDLED_PUBLISH_TASK_STORAGE_KEY)
  if (handledTaskId === task.id) return
  localStorage.setItem(HANDLED_PUBLISH_TASK_STORAGE_KEY, task.id)

  if (task.status === 'success') {
    const message = task.dryRun ? '预发布检查完成，未点击最终发布' : '全部平台发布成功'
    publishStatus.value = { message, type: 'success' }
    ElMessage.success(message)
    resetContentOnly()
    return
  }

  if (task.status === 'cancelled') {
    const message = '发布任务已停止，未提交的平台不会继续发布'
    publishStatus.value = { message, type: 'warning' }
    ElMessage.warning('发布任务已停止')
    return
  }

  const failures = (task.platforms || []).filter(platform => platform.status === 'failed')
  const detail = failures
    .map(platform => `${platform.name}：${platform.message || '发布失败'}`)
    .join('；')
  const message = detail || task.message || '发布任务失败'
  publishStatus.value = { message, type: 'error' }
  ElMessage.error(task.status === 'partial_failure' ? '部分平台发布失败' : '发布任务失败')
}

const buildInterruptedTask = (task, message = '服务已重启，原发布任务已中止') => {
  const stoppedAt = Date.now()
  return {
    ...task,
    status: 'cancelled',
    message,
    finishedAt: stoppedAt,
    platforms: (task?.platforms || []).map(platform => (
      ['success', 'failed'].includes(platform.status)
        ? platform
        : {
            ...platform,
            lastStage: platform.lastStage || platform.stage,
            stage: 'cancelled',
            status: 'cancelled',
            message: '服务重启后已停止',
            finishedAt: stoppedAt
          }
    ))
  }
}

const pollPublishTask = async (taskId) => {
  stopPublishTaskPolling()
  try {
    const response = await fetch(`${apiBaseUrl}/publishTasks/${taskId}`, {
      headers: authHeaders.value
    })
    const data = await response.json()
    if (data.code !== 200 || !data.data) {
      publishing.value = false
      localStorage.removeItem(ACTIVE_PUBLISH_TASK_STORAGE_KEY)
      if (publishTask.value?.id === taskId && !terminalTaskStatuses.has(publishTask.value.status)) {
        persistPublishTask(buildInterruptedTask(publishTask.value))
      }
      publishStatus.value = { message: data.msg || '无法读取发布进度，原任务已停止', type: 'warning' }
      return
    }

    persistPublishTask(data.data)
    publishing.value = !terminalTaskStatuses.has(data.data.status)
    if (terminalTaskStatuses.has(data.data.status)) {
      handlePublishTaskFinished(data.data)
      return
    }
  } catch (error) {
    console.warn('读取发布任务进度失败', error)
    publishStatus.value = { message: '进度连接暂时中断，正在自动重连…', type: 'warning' }
  }

  publishTaskPollTimer = setTimeout(() => pollPublishTask(taskId), 1000)
}

const restorePublishTask = () => {
  try {
    const cached = localStorage.getItem(LAST_PUBLISH_TASK_STORAGE_KEY)
    if (cached) publishTask.value = JSON.parse(cached)
  } catch (error) {
    console.warn('恢复最近发布任务失败', error)
  }
  const activeTaskId = localStorage.getItem(ACTIVE_PUBLISH_TASK_STORAGE_KEY)
  if (activeTaskId) {
    publishing.value = true
    pollPublishTask(activeTaskId)
  } else if (publishTask.value && !terminalTaskStatuses.has(publishTask.value.status)) {
    persistPublishTask(buildInterruptedTask(publishTask.value, '原发布任务已中止'))
  }
}

const stopCurrentPublishTask = async () => {
  const taskId = publishTask.value?.id
  if (!taskId || stoppingPublish.value) return

  try {
    await ElMessageBox.confirm(
      '停止后会关闭当前发布浏览器，并阻止尚未提交的平台继续发布。已经提交成功的作品无法撤回。',
      '确认停止发布？',
      {
        confirmButtonText: '停止发布',
        cancelButtonText: '继续发布',
        type: 'warning'
      }
    )
  } catch (_) {
    return
  }

  stoppingPublish.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/publishTasks/${taskId}/cancel`, {
      method: 'POST',
      headers: authHeaders.value
    })
    const data = await response.json()
    if (data.code !== 200 || !data.data) {
      throw new Error(data.msg || '停止发布失败')
    }
    persistPublishTask(data.data)
    publishStatus.value = { message: '正在停止发布，请稍候…', type: 'warning' }
    pollPublishTask(taskId)
  } catch (error) {
    const message = error?.message || '停止发布失败'
    publishStatus.value = { message, type: 'error' }
    ElMessage.error(message)
  } finally {
    stoppingPublish.value = false
  }
}

const platformByType = (type) => {
  return platformCatalog.find(item => item.type === Number(type)) || {
    type: Number(type),
    name: '未知平台',
    iconSrc: '',
    iconClass: 'unknown',
    color: '#8e8e93'
  }
}

const resolveAvatarUrl = (url) => {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  return `${apiBaseUrl}${url}`
}

const accountGroups = computed(() => {
  const map = new Map()
  accountStore.accounts.forEach(account => {
    const name = account.profileName || account.name || '未命名主体'
    if (!map.has(name)) {
      map.set(name, { name, avatarUrl: account.avatarUrl, accounts: [], normalCount: 0 })
    }
    const group = map.get(name)
    if (!group.avatarUrl && account.avatarUrl) group.avatarUrl = account.avatarUrl
    group.accounts.push({ ...account, type: Number(account.type) })
  })

  return Array.from(map.values()).map(group => {
    group.accounts.sort((a, b) => {
      return (platformOrder[a.type] ?? 99) - (platformOrder[b.type] ?? 99)
    })
    group.normalCount = group.accounts.filter(account => account.status === '正常').length
    return group
  })
})

const selectedProfileGroup = computed(() => {
  return accountGroups.value.find(group => group.name === publishForm.selectedProfileName)
})

const selectedPlatformAccounts = computed(() => {
  if (!selectedProfileGroup.value) return []
  return publishForm.selectedPlatformTypes
    .map(type => selectedProfileGroup.value.accounts.find(account => Number(account.type) === Number(type)))
    .filter(Boolean)
    .sort((a, b) => {
      return (platformOrder[Number(a.type)] ?? 99) - (platformOrder[Number(b.type)] ?? 99)
    })
})

const hasBilibili = computed(() => publishForm.selectedPlatformTypes.includes(5))

const requiredCoverSpecs = computed(() => {
  const orderedRatios = ['3:4', '4:3', '16:9']
  return orderedRatios
    .filter(ratio => publishForm.selectedPlatformTypes.some(type => {
      return (platformCoverRatios[Number(type)] || []).includes(ratio)
    }))
    .map(ratio => {
      const platformNames = publishForm.selectedPlatformTypes
        .filter(type => (platformCoverRatios[Number(type)] || []).includes(ratio))
        .map(type => platformByType(type).name)
      return {
        ...coverSpecs[ratio],
        platformNames
      }
    })
})

const coverDisplaySpecs = computed(() => {
  const requiredMap = new Map(requiredCoverSpecs.value.map(spec => [spec.ratio, spec]))
  return ['3:4', '4:3', '16:9'].map(ratio => {
    const requiredSpec = requiredMap.get(ratio)
    return {
      ...coverSpecs[ratio],
      ratioClass: `cover-drop--${ratio.replace(':', '-')}`,
      platformNames: requiredSpec?.platformNames || [],
      active: Boolean(requiredSpec)
    }
  })
})

const selectedPlatformConfigs = computed(() => {
  return publishForm.selectedPlatformTypes.map(type => getPlatformConfig(type))
})

const selectedTopicLimit = computed(() => {
  if (!selectedPlatformConfigs.value.length) return GLOBAL_TOPIC_LIMIT
  return Math.min(GLOBAL_TOPIC_LIMIT, ...selectedPlatformConfigs.value.map(config => config.topicLimit || GLOBAL_TOPIC_LIMIT))
})

const titleLimitHint = computed(() => '作品标题最多 20 字，三个平台共用')
const topicLimitHint = computed(() => `话题最多 ${selectedTopicLimit.value} 个`)

watch(selectedTopicLimit, (limit) => {
  if (publishForm.selectedTopics.length <= limit) return
  publishForm.selectedTopics = normalizeTopics(publishForm.selectedTopics, limit)
  ElMessage.warning(`已按当前平台限制保留前 ${limit} 个话题`)
})

const videoMaterials = computed(() => {
  const videoExtensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v']
  return materials.value.filter(material => {
    const filename = (material.filename || '').toLowerCase()
    return videoExtensions.some(ext => filename.endsWith(ext))
  })
})

const imageMaterials = computed(() => {
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
  return materials.value.filter(material => {
    const filename = (material.filename || '').toLowerCase()
    return imageExtensions.some(ext => filename.endsWith(ext))
  })
})

onMounted(async () => {
  restorePublishTask()
  taskClockTimer = window.setInterval(() => {
    taskClock.value = Date.now()
  }, 1000)

  try {
    const res = await accountApi.getValidAccounts({ validate: 0 })
    if (res && res.code === 200 && Array.isArray(res.data)) {
      accountStore.setAccounts(res.data)
    }
  } catch (e) {
    console.warn('初始化获取账号失败', e)
  }
})

onBeforeUnmount(() => {
  stopPublishTaskPolling()
  if (taskClockTimer) {
    clearInterval(taskClockTimer)
    taskClockTimer = null
  }
})

const selectProfile = (group) => {
  publishForm.selectedProfileName = group.name
  const normalTypes = group.accounts
    .filter(account => account.status === '正常')
    .map(account => Number(account.type))
  publishForm.selectedPlatformTypes = normalTypes.length
    ? normalTypes
    : group.accounts.map(account => Number(account.type))
}

watch(accountGroups, (groups) => {
  if (!groups.length) return
  const exists = groups.some(group => group.name === publishForm.selectedProfileName)
  if (!publishForm.selectedProfileName || !exists) {
    selectProfile(groups[0])
  }
}, { immediate: true })

watch(publishForm, persistPublishDraft, { deep: true, flush: 'sync' })

watch(() => publishForm.selectedPlatformTypes, () => {
  const validRatios = requiredCoverSpecs.value.map(spec => spec.ratio)
  Object.keys(publishForm.coverVariants).forEach(type => {
    if (!validRatios.includes(type)) {
      delete publishForm.coverVariants[type]
    }
  })
}, { deep: true })

const createUploadedFile = (response, file) => {
  const filePath = response.data.path || response.data
  const filename = String(filePath).split('/').pop()
  return {
    name: file.name,
    url: materialApi.getMaterialPreviewUrl(filename),
    path: filePath,
    size: file.size || 0,
    type: file.type || ''
  }
}

const handleVideoUploadSuccess = (response, file) => {
  if (response.code !== 200) {
    ElMessage.error(response.msg || '上传失败')
    return
  }
  publishForm.fileList.push(createUploadedFile(response, file))
  ElMessage.success('视频已添加')
}

const handleUploadError = () => {
  ElMessage.error('文件上传失败')
}

const handleCoverUploaded = (ratio, response, file) => {
  if (response.code !== 200) {
    ElMessage.error(response.msg || '封面上传失败')
    return
  }
  publishForm.coverVariants[ratio] = createUploadedFile(response, file)
  ElMessage.success(`${ratio} 封面已更新`)
}

const removeCoverVariant = (ratio) => {
  delete publishForm.coverVariants[ratio]
}

const removeVideo = (index) => {
  publishForm.fileList.splice(index, 1)
}

const ensureMaterialsLoaded = async () => {
  if (materials.value.length > 0) return true
  try {
    const response = await materialApi.getAllMaterials()
    if (response.code === 200) {
      appStore.setMaterials(response.data)
      return true
    }
  } catch (e) {
    console.error('获取素材列表出错:', e)
  }
  ElMessage.error('获取素材列表失败')
  return false
}

const openVideoLibrary = async () => {
  if (!await ensureMaterialsLoaded()) return
  selectedVideoMaterialIds.value = []
  videoLibraryVisible.value = true
}

const confirmVideoSelection = () => {
  if (!selectedVideoMaterialIds.value.length) {
    ElMessage.warning('请选择至少一个视频素材')
    return
  }
  selectedVideoMaterialIds.value.forEach(materialId => {
    const material = materials.value.find(item => item.id === materialId)
    if (!material) return
    const exists = publishForm.fileList.some(file => file.path === material.file_path)
    if (exists) return
    const filename = String(material.file_path || '').split('/').pop()
    publishForm.fileList.push({
      name: material.filename,
      url: materialApi.getMaterialPreviewUrl(filename),
      path: material.file_path,
      size: Number(material.filesize || 0) * 1024 * 1024,
      type: 'video/mp4'
    })
  })
  videoLibraryVisible.value = false
  ElMessage.success('已添加视频素材')
}

const openCoverLibrary = async (type) => {
  if (!await ensureMaterialsLoaded()) return
  coverSelectingType.value = type
  selectedCoverMaterialId.value = null
  coverLibraryVisible.value = true
}

const confirmCoverSelection = () => {
  const material = imageMaterials.value.find(item => item.id === selectedCoverMaterialId.value)
  if (!material) {
    ElMessage.warning('请选择一张封面')
    return
  }
  const filename = String(material.file_path || '').split('/').pop()
  const cover = {
    materialId: material.id,
    name: material.filename,
    url: materialApi.getMaterialPreviewUrl(filename),
    path: material.file_path,
    size: Number(material.filesize || 0) * 1024 * 1024,
    type: 'image/*'
  }
  publishForm.coverVariants[coverSelectingType.value] = cover
  coverLibraryVisible.value = false
  ElMessage.success('封面已选择')
}

const addTopic = () => {
  const topic = String(publishForm.topicDraft || '').trim().replace(/^#+/, '')
  if (!topic) return
  if (topic.length > 20) {
    ElMessage.warning('单个话题不能超过20字')
    return
  }
  if (publishForm.selectedTopics.includes(topic)) {
    publishForm.topicDraft = ''
    return
  }
  if (publishForm.selectedTopics.length >= selectedTopicLimit.value) {
    ElMessage.warning(topicLimitHint.value)
    return
  }
  publishForm.selectedTopics.push(topic)
  publishForm.topicDraft = ''
}

const removeTopic = (topic) => {
  publishForm.selectedTopics = publishForm.selectedTopics.filter(item => item !== topic)
}

const setScheduleEnabled = (enabled) => {
  publishForm.scheduleEnabled = enabled
  if (!enabled) {
    publishForm.videosPerDay = 1
    publishForm.dailyTimes = ['10:00']
    publishForm.startDays = 0
    publishForm.timeJitterMinutes = 15
  }
}

const buildPublishPayloads = () => {
  return selectedPlatformAccounts.value.map(account => {
    const type = Number(account.type)
    const platformTopicLimit = getPlatformConfig(type).topicLimit || GLOBAL_TOPIC_LIMIT
    const coverRatios = platformCoverRatios[type] || []
    const coverPaths = {}
    coverRatios.forEach(ratio => {
      const cover = publishForm.coverVariants[ratio]
      if (cover?.path) coverPaths[ratio] = cover.path
    })
    const platformCover = coverRatios
      .map(ratio => publishForm.coverVariants[ratio])
      .find(Boolean)
    const payload = {
      type,
      title: publishForm.title.trim(),
      description: publishForm.description,
      tags: normalizeTopics(publishForm.selectedTopics, platformTopicLimit),
      fileList: publishForm.fileList.map(file => file.path),
      accountList: [account.filePath],
      enableTimer: publishForm.scheduleEnabled ? 1 : 0,
      videosPerDay: publishForm.scheduleEnabled ? publishForm.videosPerDay || 1 : 1,
      dailyTimes: publishForm.scheduleEnabled ? publishForm.dailyTimes || ['10:00'] : ['10:00'],
      startDays: publishForm.scheduleEnabled ? publishForm.startDays || 0 : 0,
      timeJitterMinutes: publishForm.scheduleEnabled ? publishForm.timeJitterMinutes || 0 : 0,
      debugDryRun: debugDryRunEnabled,
      debugDryRunHoldBrowser: true,
      category: 0
    }

    if (platformCover?.path) payload.coverPath = platformCover.path
    if (Object.keys(coverPaths).length) payload.coverPaths = coverPaths
    if (type === 5) {
      payload.biliType = publishForm.biliType
      payload.biliPartition = publishForm.biliPartition
    }

    return { account, payload }
  })
}

const isNormalStatus = (status) => {
  return status === 1 || status === '1' || status === true || status === '正常'
}

const formatAccountName = (account) => {
  return account?.name || account?.userName || account?.profileName || account?.filePath || '未命名账号'
}

const askAccountCheckBeforePublish = async () => {
  try {
    await ElMessageBox.confirm(
      '建议先检测本次发布账号的登录状态。视频号等平台登录态可能会在一天左右失效，检测可以避免上传到一半才失败。',
      '发布前账号检测',
      {
        confirmButtonText: '先检测并发布',
        cancelButtonText: '跳过检测直接发布',
        distinguishCancelAndClose: true,
        closeOnClickModal: false,
        closeOnPressEscape: true,
        type: 'info',
        customClass: 'publish-preflight-dialog'
      }
    )
    return true
  } catch (action) {
    if (action === 'cancel') return false
    throw action
  }
}

const verifySelectedAccounts = async (accountsToVerify = selectedPlatformAccounts.value) => {
  const ids = accountsToVerify.map(account => account.id).filter(Boolean)
  if (!ids.length) return true
  accountChecking.value = true
  publishStatus.value = { message: '正在检测账号登录状态...', type: 'info' }
  try {
    const res = await accountApi.getValidAccounts({
      validate: 1,
      force: 1,
      ids: ids.join(',')
    })
    if (res.code === 200 && Array.isArray(res.data)) {
      accountStore.setAccounts(res.data)
      const idSet = new Set(ids.map(Number))
      const invalidAccounts = res.data.filter(account => {
        return idSet.has(Number(account.id)) && !isNormalStatus(account.status)
      })

      if (invalidAccounts.length) {
        const message = invalidAccounts
          .slice(0, 3)
          .map(account => `${platformByType(account.type).name}「${formatAccountName(account)}」`)
          .join('、')
        const suffix = invalidAccounts.length > 3 ? ` 等 ${invalidAccounts.length} 个账号` : ''
        publishStatus.value = {
          message: `账号检测未通过：${message}${suffix} 登录已失效，请先重登。`,
          type: 'warning'
        }
        ElMessage.warning('账号检测未通过，请先重登')
        return false
      }

      publishStatus.value = { message: '账号检测通过，正在进入发布流程...', type: 'success' }
      return true
    }

    publishStatus.value = { message: res.msg || '账号检测失败，请稍后重试', type: 'warning' }
    return false
  } catch (error) {
    console.error('账号检测失败:', error)
    publishStatus.value = { message: '账号检测失败，请稍后重试，或选择跳过检测直接发布。', type: 'warning' }
    return false
  } finally {
    accountChecking.value = false
  }
}

const ensurePublishReady = () => {
  const validation = validatePublishForm(publishForm)
  if (!validation.valid) return Object.values(validation.errors)[0]
  if (selectedPlatformAccounts.value.length !== publishForm.selectedPlatformTypes.length) {
    return '所选账号主体缺少对应的平台账号'
  }
  if (hasBilibili.value && !publishForm.biliPartition) {
    return '请选择B站分区'
  }
  if (hasBilibili.value) {
    const missingRatios = ['4:3', '16:9'].filter(ratio => !publishForm.coverVariants[ratio]?.path)
    if (missingRatios.length) {
      return `B站需要同时设置4:3和16:9封面，缺少${missingRatios.join('、')}封面`
    }
  }
  return ''
}

const confirmPublish = async () => {
  if (publishing.value) return
  const error = ensurePublishReady()
  if (error) {
    publishStatus.value = { message: error, type: 'error' }
    ElMessage.error(error)
    return
  }

  const payloadItems = buildPublishPayloads()
  const expectedPlatformCount = publishForm.selectedPlatformTypes.length
  if (payloadItems.length !== expectedPlatformCount) {
    publishStatus.value = { message: '所选平台账号不完整，请先补齐账号后再发布。', type: 'warning' }
    ElMessage.warning('所选平台账号不完整')
    return
  }

  let shouldCheckAccounts = true
  try {
    shouldCheckAccounts = await askAccountCheckBeforePublish()
  } catch (_) {
    return
  }

  if (shouldCheckAccounts) {
    const accountsOk = await verifySelectedAccounts(payloadItems.map(item => item.account))
    if (!accountsOk) return
  }

  publishing.value = true
  try {
    payloadItems.forEach(item => {
      item.payload.skipAccountCheck = true
    })
    const response = await fetch(`${apiBaseUrl}/publishTasks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders.value
      },
      body: JSON.stringify(payloadItems.map(item => item.payload))
    })
    const data = await response.json()
    if (data.code !== 202 || !data.data?.id) {
      throw new Error(data.msg || '创建发布任务失败')
    }

    persistPublishTask(data.data)
    publishStatus.value = { message: '发布任务已启动，可在下方查看实时进度', type: 'info' }
    ElMessage.success('发布任务已启动')
    pollPublishTask(data.data.id)
  } catch (e) {
    console.error('发布错误:', e)
    const message = e?.message || '发布失败，请检查网络连接'
    publishStatus.value = { message, type: 'error' }
    ElMessage.error(message)
    publishing.value = false
  }
}

const resetContentOnly = () => {
  publishForm.fileList = []
  publishForm.title = ''
  publishForm.description = ''
  publishForm.selectedTopics = []
  publishForm.topicDraft = ''
  publishForm.coverVariants = {}
  publishForm.scheduleEnabled = false
  publishForm.videosPerDay = 1
  publishForm.dailyTimes = ['10:00']
  publishForm.startDays = 0
  publishForm.timeJitterMinutes = 15
}

const resetForm = () => {
  resetContentOnly()
  publishForm.biliType = '自制'
  publishForm.biliPartition = ''
  publishStatus.value = null
}
</script>

<style lang="scss" scoped>
:global(.publish-preflight-dialog) {
  width: min(440px, calc(100vw - 32px));
  border-radius: 18px;
  padding: 18px;

  .el-message-box__title {
    color: #1d1d1f;
    font-size: 17px;
    font-weight: 720;
  }

  .el-message-box__message {
    color: #6e6e73;
    line-height: 1.75;
  }

  .el-message-box__btns {
    gap: 10px;
  }

  .el-button {
    border-radius: 10px;
  }
}

.publish-center {
  min-width: 0;
  min-height: 100%;
  padding: 22px 28px 36px;
  color: #16181d;
  background:
    radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.92), rgba(245, 246, 248, 0.92) 42%, #f4f5f7 100%);
}

.account-dock,
.panel {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(15, 23, 42, 0.07);
  border-radius: 18px;
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.055);
  backdrop-filter: blur(18px);
}

.dock-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;

  :deep(.el-button) {
    height: 36px;
    border-radius: 10px;
    font-weight: 650;
  }

  :deep(.el-tag) {
    height: 30px;
    padding: 0 12px;
    border-radius: 999px;
    background: rgba(248, 250, 252, 0.86);
  }
}

.account-dock {
  padding: 12px 16px 14px;
  margin-bottom: 12px;
}

.dock-head,
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;

  h2,
  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 750;
    letter-spacing: 0;
  }
}

.dock-head {
  align-items: center;
  margin-bottom: 10px;
}

.account-dock-body {
  display: grid;
  grid-template-columns: minmax(166px, 0.22fr) minmax(0, 1fr);
  gap: 10px;
  align-items: stretch;
}

.account-rail {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  min-height: 100%;
}

.account-pill {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  min-height: 66px;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  background: rgba(248, 250, 252, 0.58);
  border: 1px solid transparent;
  border-radius: 18px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;

  &:hover {
    transform: translateY(-1px);
    background: rgba(248, 250, 252, 0.82);
    box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
  }

  &.active {
    background: rgba(247, 245, 255, 0.92);
    border-color: rgba(109, 93, 252, 0.2);
    box-shadow: inset 3px 0 0 rgba(109, 93, 252, 0.9), 0 14px 34px rgba(56, 45, 76, 0.055);
  }
}

.profile-avatar {
  display: grid;
  width: 34px;
  height: 34px;
  overflow: hidden;
  place-items: center;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, #4b5563, #111827);
  border-radius: 50%;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.profile-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;

  strong,
  small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    font-size: 13px;
  }

  small {
    font-size: 11px;
    color: #8a94a6;
  }
}

.profile-platforms {
  display: none;
}

.platform-picker {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  align-items: stretch;
  padding: 0;
  min-width: 0;
  min-height: 66px;
  background: transparent;
  border: 0;
  border-radius: 0;
}

.platform-card {
  display: flex;
  flex: 1 1 0;
  align-items: center;
  min-width: 0;
  min-height: 66px;
  padding: 8px 10px;
  background: rgba(248, 250, 252, 0.62);
  border: 1px solid transparent;
  border-radius: 14px;
  transition: transform 0.16s ease, border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;

  &:hover {
    transform: translateY(-1px);
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.045);
  }

  &.disabled {
    opacity: 0.58;
  }

  :deep(.el-checkbox) {
    display: flex;
    align-items: center;
    width: 100%;
    height: 100%;
    margin: 0;
  }

  :deep(.el-checkbox__label) {
    display: grid;
    grid-template-columns: 26px minmax(0, 1fr) auto;
    align-items: center;
    gap: 7px;
    width: 100%;
    height: 100%;
    min-width: 0;
    padding-left: 7px;
    padding-right: 0;
  }

  :deep(.el-checkbox__input) {
    align-self: center;
  }

  :deep(.el-tag) {
    position: static;
    height: 22px;
    padding: 0 8px;
    margin-left: 1px;
    font-size: 11px;
    line-height: 20px;
    transform: none;
  }
}

.platform-mark,
.platform-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  overflow: hidden;
  background: #fff;
  border-radius: 9px;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.08), 0 6px 14px rgba(15, 23, 42, 0.08);

  img {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }
}

.platform-badge {
  width: 26px;
  height: 26px;
}

.platform-mark--channels img,
.platform-badge--channels img {
  width: 82%;
  height: 82%;
  object-fit: contain;
}

.platform-mark--bilibili img,
.platform-badge--bilibili img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.platform-info {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 1px;
  min-width: 0;

  strong,
  small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    font-size: 12px;
    font-weight: 760;
    line-height: 1.25;
  }

  small {
    max-width: 100%;
    font-size: 11px;
    line-height: 1.25;
    color: #8a94a6;
  }
}

.publish-progress-panel {
  margin-top: 16px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(15, 23, 42, 0.07);
  border-radius: 20px;
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.065);
}

.publish-progress-head,
.publish-progress-title-row,
.platform-progress-row,
.platform-progress-meta {
  display: flex;
  align-items: center;
}

.publish-progress-head {
  justify-content: space-between;
  gap: 20px;

  p {
    margin: 6px 0 0;
    color: #7b8494;
    font-size: 13px;
  }
}

.publish-progress-title-row {
  gap: 10px;

  h3 {
    margin: 0;
    color: #171a21;
    font-size: 17px;
  }
}

.publish-progress-summary {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  flex: 0 0 auto;

  strong {
    color: #6d5dfc;
    font-size: 23px;
    line-height: 1;
  }

  span {
    color: #8a94a6;
    font-size: 12px;
  }
}

.publish-overall-progress {
  margin-top: 17px;
}

.platform-progress-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-top: 16px;
}

.platform-progress-item {
  display: flex;
  gap: 12px;
  min-width: 0;
  padding: 14px;
  background: #f7f9fc;
  border: 1px solid #edf0f5;
  border-radius: 16px;

  &.is-success {
    background: #f2fbf6;
    border-color: #d9f0e2;
  }

  &.is-failed {
    background: #fff5f5;
    border-color: #f7dcdc;
  }

  &.is-review {
    background: #fffaf0;
    border-color: #f4e5bc;
  }

  &.is-cancelling,
  &.is-cancelled {
    background: #f8f8fa;
    border-color: #dedfe4;
  }
}

.platform-progress-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  overflow: hidden;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);

  img {
    width: 25px;
    height: 25px;
    object-fit: contain;
  }
}

.platform-progress-main {
  min-width: 0;
  flex: 1;

  > p {
    overflow: hidden;
    margin: 8px 0 0;
    color: #788294;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.platform-current-step {
  margin-top: 11px;
  color: #303846;
  font-size: 13px;
  font-weight: 720;
}

.platform-step-list {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin: 13px 0 0;
  padding: 0;
  list-style: none;

  li {
    position: relative;
    display: flex;
    min-width: 0;
    align-items: center;
    flex-direction: column;
    gap: 7px;
    color: #a0a8b6;
    text-align: center;

    &:not(:last-child)::after {
      position: absolute;
      z-index: 0;
      top: 13px;
      left: calc(50% + 16px);
      width: calc(100% - 32px);
      height: 2px;
      background: #dfe4eb;
      content: '';
    }

    &.complete {
      color: #24a865;

      .platform-step-dot,
      &:not(:last-child)::after {
        color: #fff;
        background: #35b979;
        border-color: #35b979;
      }
    }

    &.active {
      color: #6d5dfc;
      font-weight: 720;

      .platform-step-dot {
        color: #fff;
        background: #6d5dfc;
        border-color: #6d5dfc;
        box-shadow: 0 0 0 5px rgba(109, 93, 252, 0.12);
      }
    }

    &.failed {
      color: #e34d59;
      font-weight: 720;

      .platform-step-dot {
        color: #fff;
        background: #e34d59;
        border-color: #e34d59;
      }
    }

    &.cancelled,
    &.skipped {
      color: #7c8594;

      .platform-step-dot {
        color: #fff;
        background: #929aa7;
        border-color: #929aa7;
      }
    }
  }
}

.platform-step-dot {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  background: #fff;
  border: 2px solid #dfe4eb;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 800;
}

.platform-step-name {
  overflow: hidden;
  width: 100%;
  font-size: 11px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-progress-row {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 9px;

  > div:first-child {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 2px;
  }

  strong {
    color: #20242c;
    font-size: 14px;
  }

  span {
    color: #8993a4;
    font-size: 11px;
  }
}

.platform-progress-meta {
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.publish-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(15, 23, 42, 0.07);
  border-radius: 18px;
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.065);
  backdrop-filter: blur(18px);

  :deep(.el-button) {
    min-width: 176px;
    height: 42px;
    border-radius: 12px;
    font-weight: 760;
  }
}

.publish-action-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;

  strong {
    color: #16181d;
    font-size: 14px;
    font-weight: 780;
  }

  span {
    overflow: hidden;
    color: #8a94a6;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.publish-action-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(380px, 0.9fr) minmax(460px, 1.1fr);
  gap: 16px;
  align-items: start;
}

.panel {
  min-width: 0;
  padding: 17px;

  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner),
  :deep(.el-select__wrapper) {
    border-radius: 12px;
    box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.08) inset;
    transition: box-shadow 0.16s ease, background 0.16s ease;
  }

  :deep(.el-input__wrapper:hover),
  :deep(.el-textarea__inner:hover),
  :deep(.el-select__wrapper:hover) {
    box-shadow: 0 0 0 1px rgba(109, 93, 252, 0.28) inset;
  }

  :deep(.el-form-item__label) {
    margin-bottom: 7px;
    color: #555f70;
    font-size: 12px;
    font-weight: 700;
  }

  :deep(.el-button) {
    border-radius: 10px;
    font-weight: 650;
  }
}

.media-panel,
.cover-panel {
  --publish-tray-height: 318px;
  grid-column: span 1;
  height: 386px;
  overflow: hidden;
}

.media-panel {
  display: flex;
  flex-direction: column;
}

.content-panel,
.schedule-panel {
  grid-column: 1 / -1;
}

.drop-upload {
  display: flex;
  flex: 1;
  min-height: 0;
  width: 100%;

  :deep(.el-upload) {
    display: flex;
    width: 100%;
    flex: 1;
  }

  :deep(.el-upload-dragger) {
    display: flex;
    align-items: stretch;
    justify-content: center;
    width: 100%;
    height: var(--publish-tray-height);
    min-height: 0;
    padding: 16px;
    overflow-y: scroll;
    overscroll-behavior: contain;
    scrollbar-gutter: stable;
    background: rgba(248, 250, 252, 0.72);
    border-color: rgba(15, 23, 42, 0.08);
    border-radius: 16px;
    transition: background 0.18s ease, border-color 0.18s ease;

    &:hover {
      background: rgba(248, 246, 255, 0.94);
      border-color: rgba(109, 93, 252, 0.46);
    }

    &::-webkit-scrollbar {
      width: 8px;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(148, 163, 184, 0.42);
      border: 2px solid rgba(248, 250, 252, 0.72);
      border-radius: 999px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }
  }
}

.drop-empty-state {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.drop-icon {
  width: 42px;
  height: 42px;
  margin-bottom: 2px;
  color: #6d5dfc;
}

.drop-title {
  font-size: 15px;
  font-weight: 750;
}

.drop-subtitle {
  margin-top: 6px;
  font-size: 12px;
  color: #8a94a6;
}

.drop-library-button {
  margin-top: 12px;
}

.video-file-list {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 8px;
  align-content: start;
}

.video-file-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  height: 48px;
  min-height: 48px;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(15, 23, 42, 0.07);
  border-radius: 12px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.045);
}

.video-file-index {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  color: #5b4cdc;
  font-size: 12px;
  font-weight: 800;
  background: rgba(109, 93, 252, 0.11);
  border-radius: 9px;
}

.video-file-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  text-align: left;

  strong,
  small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    color: #1d2433;
    font-size: 13px;
    font-weight: 750;
  }

  small {
    color: #8a94a6;
    font-size: 11px;
  }
}

.video-drop-hint {
  display: flex;
  min-height: 82px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  color: #8a94a6;
  background: rgba(255, 255, 255, 0.66);
  border: 1px dashed rgba(109, 93, 252, 0.3);
  border-radius: 14px;

  span {
    font-size: 12px;
    font-weight: 650;
  }
}

.cover-layout {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  height: var(--publish-tray-height);
  min-height: 0;
}

.cover-card {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  padding: 12px;
  background: rgba(248, 250, 252, 0.72);
  border: 1px solid rgba(15, 23, 42, 0.07);
  border-radius: 15px;
  overflow: hidden;
  transition: background 0.16s ease, border-color 0.16s ease, opacity 0.16s ease;

  &.is-inactive {
    background: rgba(248, 250, 252, 0.42);
    border-color: rgba(15, 23, 42, 0.045);

    .cover-spec span,
    .cover-spec strong {
      color: #a4adba;
    }
  }
}

.cover-spec {
  display: flex;
  min-height: 45px;
  flex-direction: column;
  justify-content: flex-start;
  min-width: 0;
  gap: 3px;

  span {
    overflow: hidden;
    font-size: 12px;
    color: #6d5dfc;
    font-weight: 750;
    line-height: 1.35;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    font-size: 20px;
    line-height: 1.1;
  }

  small {
    font-size: 12px;
    color: #8a94a6;
  }
}

.cover-stage {
  display: flex;
  flex: 1;
  min-height: 0;
  align-items: center;
  justify-content: center;
  padding: 6px 0 10px;
  overflow: hidden;
}

.cover-drop {
  display: flex;
  min-width: 0;
  min-height: 0;
  max-width: 100%;
  max-height: 100%;
}

.cover-drop--3-4 {
  width: min(100%, 126px);
  aspect-ratio: 3 / 4;
}

.cover-drop--4-3 {
  width: min(100%, 190px);
  aspect-ratio: 4 / 3;
}

.cover-drop--16-9 {
  width: min(100%, 220px);
  aspect-ratio: 16 / 9;
}

:deep(.cover-drop .el-upload) {
  display: flex;
  min-width: 0;
  min-height: 0;
  width: 100%;
  height: 100%;
}

:deep(.cover-drop .el-upload-dragger) {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: 0;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.92);
  border-color: rgba(15, 23, 42, 0.08);
  border-radius: 13px;
}

:deep(.cover-drop.is-disabled .el-upload-dragger) {
  cursor: default;
  background: rgba(248, 250, 252, 0.6);
  border-color: rgba(15, 23, 42, 0.045);
}

:deep(.cover-thumb),
:deep(.cover-empty) {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  height: 100%;
  min-width: 0;
  margin: 0;
}

:deep(.cover-thumb img) {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

:deep(.cover-empty) {
  display: flex;
  min-width: 74px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 8px;
  color: #8a94a6;
  background: linear-gradient(180deg, #ffffff, #f7f9fc);
}

:deep(.cover-empty span) {
  display: block;
  margin-top: 4px;
  font-size: 11px;
}

:deep(.cover-empty-icon) {
  width: 20px;
  height: 20px;
  color: #6d5dfc;
}

:deep(.cover-tools) {
  display: flex;
  min-height: 32px;
  gap: 8px;
  align-items: center;
  justify-content: center;
}

.topic-editor {
  width: 100%;
}

.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-content: flex-start;
  min-height: 34px;
  max-height: 70px;
  padding: 2px 0;
  margin-bottom: 10px;
  overflow-y: auto;
}

.topic-placeholder {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 10px;
  color: #a0a8b5;
  font-size: 12px;
  background: rgba(248, 250, 252, 0.74);
  border: 1px dashed rgba(148, 163, 184, 0.32);
  border-radius: 999px;
}

.topic-input-row,
.form-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}

.form-grid {
  grid-template-columns: minmax(180px, 240px) 1fr;
}

.bili-settings-inline {
  margin-top: 4px;
  padding: 16px;
  background: rgba(109, 93, 252, 0.045);
  border: 1px solid rgba(109, 93, 252, 0.12);
  border-radius: 14px;

  .form-grid :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.bili-settings-inline__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;

  h4 {
    margin: 0;
    color: #252238;
    font-size: 14px;
  }

  span {
    color: #9390a3;
    font-size: 12px;
  }
}

.title-textarea {
  :deep(.el-textarea__inner) {
    min-height: 92px !important;
    line-height: 1.55;
  }
}

.schedule-panel {
  :deep(.schedule-section) {
    margin-bottom: 0;
  }

  :deep(.schedule-section h3) {
    display: none;
  }
}

.floating-status {
  position: sticky;
  bottom: 16px;
  z-index: 6;
  max-width: 980px;
  margin: 16px auto 0;
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.1);
}

.library-content {
  max-height: 420px;
  overflow: auto;
}

.material-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.material-item {
  padding: 12px;
  background: rgba(248, 250, 252, 0.72);
  border: 1px solid rgba(15, 23, 42, 0.07);
  border-radius: 12px;

  :deep(.el-checkbox),
  :deep(.el-radio) {
    width: 100%;
    height: auto;
  }
}

.material-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;

  strong {
    color: #111827;
  }

  small {
    color: #8a94a6;
  }
}

@media (max-width: 980px) {
  .workspace-grid,
  .account-dock-body,
  .form-grid,
  .topic-input-row {
    grid-template-columns: 1fr;
  }

  .account-pill {
    min-height: 72px;
  }

  .platform-picker {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    min-height: 0;
  }

  .cover-layout {
    grid-template-columns: repeat(3, minmax(150px, 1fr));
    grid-template-rows: 1fr;
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .cover-card:nth-child(3) {
    grid-column: auto;
  }

  .dock-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .dock-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .publish-action-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .publish-action-bar :deep(.el-button) {
    width: 100%;
  }

  .publish-action-buttons {
    width: 100%;
    align-items: stretch;
    flex-direction: column-reverse;
  }
}

@media (max-width: 640px) {
  .publish-center {
    padding: 14px;
  }

  .account-pill {
    grid-template-columns: 36px minmax(0, 1fr);
  }
}
</style>
