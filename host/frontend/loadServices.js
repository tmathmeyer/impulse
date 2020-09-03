
class HostView extends HTMLElement {
  constructor() {
    super();
    this._name = null;
    this._status = "undetermined";
    this._paths = {}

    this.attachShadow({mode: 'open'});
    this._name_span = document.createElement('div');
    this._status_span = document.createElement('div');
    this._paths_span = document.createElement('div');
    this.shadowRoot.appendChild(this._name_span);
    this.shadowRoot.appendChild(this._status_span);
    this.shadowRoot.appendChild(this._paths_span);
  }

  set url(val) {
    const setContent = this._setContent.bind(this);
    fetch(val, {method: 'GET'}).then(r => {
      if (r.status / 100 != 2)
        r.json().then(console.log);
      else
        r.json().then(setContent);
    });
  }

  _setContent(content) {
    this._name = content['name'];
    this._paths = content['paths'];
    this._status = content['status'];

    this._name_span.textContent = this._name;
    this._status_span.textContent = this._status;
    this._paths_span.textContent = JSON.stringify(this._paths);
  }

  get name() {
    return this._name;
  }

  get status() {
    return this._status;
  }

  get paths() {
    return this._paths;
  }
}
window.customElements.define('host-view', HostView);


function loadHost(url) {
  const view = document.createElement('host-view');
  view.url = url;
  document.getElementById('content').appendChild(view);
}

function loadHosts(url) {
  fetch(url, {
      method: 'GET',
  }).then(r => {
    if (r.status / 10 != 20) {
      r.json().then(console.log);
    }
    r.json().then(json => {
      for (host of json) {
        loadHost(host['_links']['self']['href'])
      }
    });
  });
}

loadHosts('/api/host/alive');
console.log('foo');