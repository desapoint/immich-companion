import { mount } from 'svelte';

import App from './app/App.svelte';
import AppRuntimeError from './app/components/AppRuntimeError.svelte';
import { errorMessage } from './lib/utils/errors';
import { legacyV2RedirectPath } from './app/navigation';
import './styles/reset.css';

const target = document.getElementById('app');
const legacyRedirect = legacyV2RedirectPath(window.location.pathname);

if (legacyRedirect) {
  const suffix = `${window.location.search}${window.location.hash}`;
  window.history.replaceState(null, '', `${legacyRedirect}${suffix}`);
}

if (!target) {
  throw new Error('The frontend mount element is missing.');
}

const mountTarget: HTMLElement = target;

async function bootstrap(): Promise<void> {
  try {
    mount(App, { target: mountTarget });
  } catch (error) {
    mountTarget.replaceChildren();
    mount(AppRuntimeError, {
      target: mountTarget,
      props: {
        message: errorMessage(error),
        onretry: () => window.location.reload(),
      },
    });
  }
}

void bootstrap();
