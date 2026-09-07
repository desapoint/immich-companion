import { mount } from 'svelte';

import App from './app/App.svelte';
import AppRuntimeError from './app/components/AppRuntimeError.svelte';
import { errorMessage } from './lib/utils/errors';
import './styles/reset.css';

const target = document.getElementById('app');
const currentPath = window.location.pathname;
const isV2 = currentPath === '/v2' || currentPath.startsWith('/v2/');

if (!target) {
  throw new Error('The frontend mount element is missing.');
}

async function bootstrap(): Promise<void> {
  try {
    if (!isV2) {
      await import('./styles/global.css');
    }

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
}

void bootstrap();
