<template>
  <div id="app">
    <el-container>
      <el-aside :width="isCollapse ? '64px' : '200px'">
        <div class="sidebar">
          <div class="logo">
            <img v-show="isCollapse" src="/vite.svg" alt="Logo" class="logo-img">
            <h2 v-show="!isCollapse">自媒体一键分发</h2>
          </div>
          <el-menu
            :router="true"
            :default-active="activeMenu"
            :collapse="isCollapse"
            class="sidebar-menu"
            background-color="#f8f7fb"
            text-color="#565269"
            active-text-color="#6d5dfc"
          >
            <el-menu-item index="/account-management">
              <el-icon><User /></el-icon>
              <span>账号管理</span>
            </el-menu-item>
            <el-menu-item index="/material-management">
              <el-icon><Picture /></el-icon>
              <span>素材管理</span>
            </el-menu-item>
            <el-menu-item index="/publish-center">
              <el-icon><Upload /></el-icon>
              <span>发布中心</span>
            </el-menu-item>
          </el-menu>
          <div class="sidebar-links" :class="{ collapsed: isCollapse }">
            <el-tooltip content="我的B站主页" placement="right" :disabled="!isCollapse">
              <button type="button" class="sidebar-link" @click="openExternal('https://space.bilibili.com/3493134310836643')">
                <el-icon><VideoPlay /></el-icon>
                <span v-show="!isCollapse">我的B站主页</span>
              </button>
            </el-tooltip>
          </div>
        </div>
      </el-aside>
      <el-container>
        <el-header>
          <div class="header-content">
            <div class="header-left">
              <el-icon class="toggle-sidebar" @click="toggleSidebar"><Fold /></el-icon>
            </div>
            <div class="header-right">
              <!-- 账号信息已移除 -->
            </div>
          </div>
        </el-header>
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  User, Fold, Picture, Upload, VideoPlay
} from '@element-plus/icons-vue'

const route = useRoute()

// 当前激活的菜单项
const activeMenu = computed(() => {
  return route.path
})

// 侧边栏折叠状态
const isCollapse = ref(false)

// 切换侧边栏折叠状态
const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}

const openExternal = (url) => {
  window.open(url, '_blank', 'noopener,noreferrer')
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

#app {
  min-height: 100vh;
}

.el-container {
  height: 100vh;
  min-width: 0;
}

.el-aside {
  background: linear-gradient(180deg, #fbfaff 0%, #f6f4fb 100%);
  color: #302d42;
  border-right: 1px solid #e6e1ee;
  height: 100vh;
  overflow: hidden;
  transition: width 0.3s;
  
  .sidebar {
    display: flex;
    flex-direction: column;
    height: 100%;
    
    .logo {
      height: 60px;
      padding: 0 16px;
      display: flex;
      align-items: center;
      background: rgba(255, 255, 255, 0.72);
      border-bottom: 1px solid #e8e3ef;
      overflow: hidden;
      
      .logo-img {
        width: 32px;
        height: 32px;
        margin-right: 12px;
      }
      
      h2 {
        color: #2e2a40;
        font-size: 16px;
        font-weight: 600;
        white-space: nowrap;
        margin: 0;
      }
    }
    
    .sidebar-menu {
      border-right: none;
      flex: 1;
      background: transparent !important;
      
      .el-menu-item {
        display: flex;
        align-items: center;
        
        .el-icon {
          margin-right: 10px;
          font-size: 18px;
        }
      }

      :deep(.el-menu-item) {
        color: #5f5a70 !important;
        transition: color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
      }

      :deep(.el-menu-item:hover) {
        color: #3b3554 !important;
        background: rgba(109, 93, 252, 0.07) !important;
      }

      :deep(.el-menu-item.is-active) {
        color: #6252ec !important;
        background: linear-gradient(90deg, rgba(109, 93, 252, 0.15), rgba(109, 93, 252, 0.05)) !important;
        box-shadow: inset 3px 0 0 #6d5dfc;
      }
    }

    .sidebar-links {
      margin: 10px 12px 14px;
      padding-top: 12px;
      border-top: 1px solid #e6e1ee;
      display: grid;
      gap: 8px;

      .sidebar-link {
        width: 100%;
        height: 36px;
        border: 1px solid #ded8e8;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.76);
        color: #5d576e;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 8px;
        padding: 0 12px;
        cursor: pointer;
        font-size: 13px;
        font-weight: 600;
        transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;

        .el-icon {
          flex: 0 0 auto;
          font-size: 15px;
        }

        &:hover {
          background: rgba(109, 93, 252, 0.09);
          border-color: rgba(109, 93, 252, 0.28);
          color: #5748d8;
        }
      }

      &.collapsed {
        margin: 10px 8px 14px;

        .sidebar-link {
          justify-content: center;
          padding: 0;
        }
      }
    }
  }
}

.el-header {
  background: rgba(255, 253, 249, 0.94);
  border-bottom: 1px solid #ece6df;
  box-shadow: 0 3px 14px rgba(56, 45, 76, 0.05);
  padding: 0;
  height: 60px;
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 100%;
    padding: 0 16px;
    
    .header-left {
      .toggle-sidebar {
        font-size: 20px;
        cursor: pointer;
        color: $text-regular;
        
        &:hover {
          color: $primary-color;
        }
      }
    }
    
    .header-right {
      .user-dropdown {
        display: flex;
        align-items: center;
        cursor: pointer;
        
        .username {
          margin: 0 8px;
          color: $text-regular;
        }
        
        .el-icon {
          font-size: 12px;
          color: $text-secondary;
        }
      }
    }
  }
}

.el-main {
  background:
    radial-gradient(circle at 88% 4%, rgba(109, 93, 252, 0.07), transparent 28%),
    radial-gradient(circle at 10% 96%, rgba(47, 183, 163, 0.055), transparent 24%),
    $bg-color-page;
  padding: 20px;
  overflow-y: auto;
  min-width: 0;
}
</style>
