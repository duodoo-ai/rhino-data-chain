//核算机构列表视图
odoo.define('base_cw.orgListView', function (require) {
    "use strict";
    var ListView = require('web.ListView');
    var viewRegistry = require('web.view_registry');
    var ListController = require('web.ListController');
    var newListController = ListController.extend({

        renderButtons: function () {
            this.ac_url_suffix=this.modelName;
            this._super.apply(this, arguments);
            if (this.$buttons) {

            };
        },


    });
    var newListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: newListController,
        }),
    });
    viewRegistry.add('orgListView', newListView);
    return newListView;
});