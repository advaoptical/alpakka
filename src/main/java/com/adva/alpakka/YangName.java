package com.adva.alpakka;

import javax.annotation.Nonnegative;

import lombok.Getter;
import lombok.NonNull;

import one.util.streamex.StreamEx;
import org.apache.commons.lang3.StringUtils;

import org.opendaylight.yangtools.yang.common.QName;
import org.opendaylight.yangtools.yang.common.XMLNamespace;


public class YangName implements CharSequence {

    @NonNull
    private final String name;

    @NonNull @Getter
    private final XMLNamespace namespace;

    public YangName(@NonNull final QName qName) {
        this.name = qName.getLocalName();
        this.namespace = qName.getNamespace();
    }

    @NonNull
    public String toPythonName() {
        return this.name.replace('-', '_');
    }

    @NonNull
    public String toPythonClassName() {
        return StreamEx.of(this.name.split("-")).map(StringUtils::capitalize).joining();
    }

    @NonNull @Override
    public String toString() {
        return this.name;
    }

    @Nonnegative @Override
    public int length() {
        return this.name.length();
    }

    @Override
    public char charAt(@Nonnegative final int index) {
        return this.name.charAt(index);
    }

    @NonNull @Override
    public CharSequence subSequence(@Nonnegative final int start, @Nonnegative final int end) {
        return this.name.subSequence(start, end);
    }
}
