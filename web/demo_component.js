
import { Component } from '/component.js'

class HostView extends Component {
  constructor() {
    super(['src']);
    this._src = null;
  }

  _onHookedAttributeChanged(attr, value, resolve, reject) {
    if (attr == 'src')
      this._setSrc(value, resolve, reject);
  }

  _setSrc(src, resolve, reject) {
    fetch(src, {method: 'GET'}).then(r => {
      if (r.status / 100 != 2) {
        reject(r);
      } else {
        r.json().then(j => {
          console.log(j);
          resolve();
        })
      }
    });
  }
};


window.customElements.define('host-view', HostView);