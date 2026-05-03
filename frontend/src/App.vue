<template>
  <div class="flex flex-col w-full h-full">
    <!-- Navbar -->
    <AppNavBar @open-existing-results="onOpenExistingResults"/>
    <!-- Page content -->
    <RouterView class="w-full h-full" />
  </div>
</template>

<script>
import { RouterLink, RouterView } from 'vue-router'
import AppNavBar from "@/components/AppNavBar.vue";
import useDialogStore from "@/stores/dialog";

export default {
  name: "App",
  components: {
    RouterLink, RouterView,
    AppNavBar
  },
  computed: {},
  methods: {
    onOpenExistingResults() {
      // Handle the event when existing results are opened
      const dialogStore = useDialogStore();
      dialogStore.existingResultsDialogVisible = true;
    }
  }
}

</script>

<style lang="scss">
@import url("../node_modules/ol/ol.css");

</style>