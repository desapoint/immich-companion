import { mount } from 'svelte';

import App from './app/App.svelte';
import AppRuntimeError from './app/components/AppRuntimeError.svelte';
import { errorMessage } from './lib/utils/errors';
import './styles/global.css';

const target = document.getElementById('app');

if (!target) {
  throw new Error('The frontend mount element is missing.');
}

try {
  mount(App, { target });
} catch (error) {
  target.replaceChildren();
  mount(AppRuntimeError, {
    target,
    props: {
      message: errorMessage(error),
      onretry: () => window.location.reload(),
    },
  });
}
