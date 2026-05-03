import './assets/main.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';
import PrimeVue from "primevue/config";
import Aura from "@primevue/themes/aura";
import { Form } from "@primevue/forms";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import FloatLabel from 'primevue/floatlabel';
import IftaLabel from 'primevue/iftalabel';
import Textarea from 'primevue/textarea';
import Checkbox from 'primevue/checkbox';
import Message from 'primevue/message';
import FileUpload from 'primevue/fileupload';
import Toast from 'primevue/toast';
import ToastService from 'primevue/toastservice';
import ListBox from "primevue/listbox";
import Tooltip from 'primevue/tooltip';
import Dialog from 'primevue/dialog';
import Select from 'primevue/select';
import DatePicker from 'primevue/datepicker';
import RadioButton from 'primevue/radiobutton';

import 'primeicons/primeicons.css'

import App from './App.vue';
import router from './router';

const app = createApp(App);

app.use(PrimeVue, {
    theme: {
        preset: Aura
    }
});

app.use(ToastService);

app.component("PrimeForm", Form);
app.component("PrimeButton", Button);
app.component("PrimeInputText", InputText);
app.component("PrimeFloatLabel", FloatLabel);
app.component("PrimeIftaLabel", IftaLabel);
app.component("PrimeTextarea", Textarea);
app.component("PrimeSelect", Select);
app.component("PrimeCheckbox", Checkbox);
app.component("PrimeDatePicker", DatePicker);
app.component("PrimeMessage", Message);
app.component("PrimeFileUpload", FileUpload);
app.component("PrimeToast", Toast);
app.component("PrimeListBox", ListBox);
app.component("PrimeDialog", Dialog);
app.component("PrimeRadioButton", RadioButton);
app.directive("tooltip", Tooltip);

app.use(createPinia());
app.use(router);

app.mount('#app');